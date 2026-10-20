"use client";

import { useEffect, useRef, type RefObject } from "react";

import { clamp, lerp, usePrefersReducedMotion, whenIdle } from "@/lib/animation";
import {
  cloudLayout,
  createParticles,
  drawParticles,
  fanLayout,
  hash01,
  ribbonLayout,
  seamLayout,
  sphereLayout,
  updateParticles,
  type LayoutPoint,
} from "@/lib/canvas-particles";

/**
 * The story's scroll progress (0–1) spans this many chapter heights: four chapters, each pinned
 * for one viewport and then scrolled away for another.
 */
export const STAGES = 8;

const COLOR = {
  chalk: "#DCE6F2",
  neon: "#00F59B",
  ice: "#00E5FF",
  amber: "#FFB800",
};

interface Geometry {
  ball: { x: number; y: number; r: number };
  ribbon: { x0: number; y0: number; w: number; h: number };
  fan: { x: number; y: number; w: number; h: number };
}

/** Where the ball, the ribbon and the fan sit. Mirrors `.landing-stage` in app/globals.css. */
export function stageGeometry(w: number, h: number, wide: boolean): Geometry {
  return wide
    ? {
        ball: { x: 0.7 * w, y: 0.52 * h, r: Math.min(0.22 * w, 0.3 * h) },
        ribbon: { x0: 0.06 * w, y0: 0.4 * h, w: 0.88 * w, h: 0.46 * h },
        fan: { x: 0.44 * w, y: 0.56 * h, w: 0.5 * w, h: 0.66 * h },
      }
    : {
        ball: { x: 0.5 * w, y: 0.7 * h, r: Math.min(0.3 * w, 0.15 * h) },
        ribbon: { x0: 0.06 * w, y0: 0.46 * h, w: 0.88 * w, h: 0.38 * h },
        fan: { x: 0.08 * w, y: 0.72 * h, w: 0.84 * w, h: 0.3 * h },
      };
}

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

type Shape = "sphere" | "cloud" | "ribbon" | "fan";

/** The shape (or the two being morphed between) at story position `s` (0–STAGES). */
function stageAt(s: number): { from: Shape; to: Shape | null; mix: number } {
  if (s < 1) return { from: "sphere", to: null, mix: 0 };
  if (s < 2.4) return { from: "sphere", to: "cloud", mix: (s - 1) / 1.4 };
  if (s < 3) return { from: "cloud", to: null, mix: 0 };
  if (s < 4.4) return { from: "cloud", to: "ribbon", mix: (s - 3) / 1.4 };
  if (s < 5) return { from: "ribbon", to: null, mix: 0 };
  if (s < 6.4) return { from: "ribbon", to: "fan", mix: (s - 5) / 1.4 };
  return { from: "fan", to: null, mix: 0 };
}

interface Look {
  alpha: number;
  size: number;
  color: string;
}

/**
 * The particle field behind the landing story: a cricket ball (with its seam) that the visitor
 * zooms into, then every ball as a point cloud, the 2019 IPL final's win-probability ribbon, and
 * simulated outcomes fanning out, before it dissolves into the competition picker.
 *
 * Reads `scrollProgress` (0–1, a ref so scrolling doesn't re-render) every frame. Draws only while
 * on screen and the tab is visible, and renders nothing for reduced motion.
 */
export function ParticleCanvas({
  scrollProgress,
  ribbon,
  className,
}: {
  scrollProgress: RefObject<number>;
  /** Team A's win probability through the match: [t, wp]. */
  ribbon: [number, number][];
  className?: string;
}) {
  const reduced = usePrefersReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (reduced || !canvas || !ctx) return;

    let w = 0;
    let h = 0;
    let wide = false;
    let geometry = stageGeometry(1, 1, false);
    let count = 0;
    let seamCount = 0;
    let particles: ReturnType<typeof createParticles> = [];
    let baseSize: number[] = [];
    let baseAlpha: number[] = [];
    let cloud: LayoutPoint[] = [];
    let ribbonPx: { x: number; y: number }[] = [];
    const targets: { x: number; y: number }[] = [];
    // Team A's win probability by horizontal position, to colour the ribbon by who is ahead.
    const wpByX = new Float32Array(256);

    function resize() {
      if (!canvas || !ctx) return;
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      wide = window.matchMedia("(min-width: 1024px)").matches;
      const dpr = Math.min(window.devicePixelRatio || 1, wide ? 1.75 : 1.5);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      geometry = stageGeometry(w, h, wide);

      const wanted = window.innerWidth < 768 ? 1400 : 3000;
      if (wanted !== count) {
        count = wanted;
        seamCount = Math.round(count * 0.18);
        particles = createParticles(
          { count, colors: [COLOR.chalk], maxSize: wide ? 1.7 : 1.5, dampening: 0.12 },
          w,
          h,
        );
        baseSize = particles.map((p) => p.size);
        baseAlpha = particles.map((p) => p.alpha);
        targets.length = 0;
        for (let i = 0; i < count; i++) targets.push({ x: 0, y: 0 });
      }
      cloud = cloudLayout(count, w, h);
      const r = geometry.ribbon;
      ribbonPx = ribbon.map(([t, wp]) => ({ x: r.x0 + t * r.w, y: r.y0 + (1 - wp) * r.h }));
      let k = 0;
      for (let b = 0; b < wpByX.length; b++) {
        const t = b / (wpByX.length - 1);
        while (k < ribbon.length - 2 && ribbon[k + 1][0] < t) k++;
        const [t0, a] = ribbon[k] ?? [0, 0.5];
        const [t1, c] = ribbon[k + 1] ?? [1, a];
        wpByX[b] = lerp(a, c, clamp((t - t0) / (t1 - t0 || 1), 0, 1));
      }
    }

    function layout(shape: Shape, s: number, time: number): LayoutPoint[] {
      const { ball, fan } = geometry;
      switch (shape) {
        case "sphere": {
          // The camera closes in on the seam through the first chapter.
          const zoom = easeInOut(clamp(s, 0, 1));
          const radius = ball.r * (1 + 0.5 * zoom);
          const rotation = time * 0.22 + s * 0.9;
          const seam = seamLayout(seamCount, ball.x, ball.y, radius, rotation);
          const body = sphereLayout(count - seamCount, ball.x, ball.y, radius, rotation);
          return seam.concat(body);
        }
        case "cloud":
          return cloud;
        case "ribbon":
          return ribbonLayout(count, ribbonPx, wide ? 7 : 5, (time * 0.03) % 1);
        case "fan":
          return fanLayout(count, { x: fan.x, y: fan.y }, fan.w, fan.h, (time * 0.05) % 1);
      }
    }

    function look(shape: Shape, i: number, p: LayoutPoint, s: number): Look {
      const depth = p.depth ?? 1;
      const size = baseSize[i];
      const alpha = baseAlpha[i];
      switch (shape) {
        case "sphere": {
          const zoom = clamp(s, 0, 1);
          if (i < seamCount) {
            return {
              alpha: (0.3 + 0.7 * depth) * (0.65 + 0.35 * zoom),
              size: size * (1.15 + 0.5 * zoom) * (0.7 + 0.5 * depth),
              color: COLOR.neon,
            };
          }
          return {
            alpha: alpha * (0.12 + 0.6 * depth),
            size: size * (0.55 + 0.55 * depth),
            color: COLOR.chalk,
          };
        }
        case "cloud":
          return {
            alpha: alpha * (0.35 + 0.55 * depth),
            size: size * 0.85,
            color: i % 11 === 0 ? COLOR.ice : i % 17 === 0 ? COLOR.neon : COLOR.chalk,
          };
        case "ribbon": {
          const r = geometry.ribbon;
          const bucket = Math.round(clamp((p.x - r.x0) / (r.w || 1), 0, 1) * (wpByX.length - 1));
          return {
            alpha: 0.2 + 0.8 * depth,
            size: size * (0.65 + 0.55 * depth),
            color: wpByX[bucket] >= 0.5 ? COLOR.neon : COLOR.amber,
          };
        }
        case "fan":
          return {
            alpha: 0.12 + 0.88 * depth ** 1.6,
            size: size * (0.55 + 0.6 * depth),
            color: depth > 0.86 ? COLOR.neon : COLOR.ice,
          };
      }
    }

    let frame = 0;
    let running = false;
    let onScreen = true;

    function draw(now: number) {
      frame = 0;
      if (!canvas || !ctx) return;
      const time = now / 1000;
      const s = clamp(scrollProgress.current ?? 0, 0, 1) * STAGES;
      const fade = s > 7 ? 1 - easeInOut(clamp(s - 7, 0, 1)) : 1;
      ctx.clearRect(0, 0, w, h);
      if (fade <= 0.001) {
        schedule();
        return;
      }

      const { from, to, mix } = stageAt(s);
      const a = layout(from, s, time);
      const b = to ? layout(to, s, time) : null;
      const steady = b === null;
      for (let i = 0; i < count; i++) {
        // Each particle leaves on its own beat, so shapes break up and gather rather than slide.
        const own = b ? easeInOut(clamp((mix - hash01(i, 29) * 0.4) / 0.6, 0, 1)) : 0;
        const pa = a[i];
        const pb = b ? b[i] : pa;
        const drift = Math.sin(time * 0.8 + i * 1.7) * (from === "cloud" && steady ? 2.2 : 0.8);
        targets[i].x = lerp(pa.x, pb.x, own) + drift;
        targets[i].y = lerp(pa.y, pb.y, own) + Math.cos(time * 0.7 + i * 2.3) * 0.8;
        // A particle that wrapped round a flowing ribbon or fan jumps rather than streaking back.
        if (steady && Math.abs(targets[i].x - particles[i].x) > w * 0.3) {
          particles[i].x = targets[i].x;
          particles[i].y = targets[i].y;
        }
        // Positions ease towards the targets below; the look changes at once.
        const la = look(from, i, pa, s);
        const lb = b && to ? look(to, i, pb, s) : la;
        particles[i].alpha = lerp(la.alpha, lb.alpha, own) * fade;
        particles[i].size = lerp(la.size, lb.size, own);
        particles[i].color = own < 0.5 ? la.color : lb.color;
      }
      updateParticles(particles, targets, from === "sphere" && steady ? 0.2 : 0.1);
      ctx.globalCompositeOperation = "lighter";
      drawParticles(ctx, particles);
      ctx.globalCompositeOperation = "source-over";
      schedule();
    }

    function schedule() {
      if (running && onScreen && !document.hidden && !frame) {
        frame = requestAnimationFrame(draw);
      }
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    const visibility = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting;
      schedule();
    });
    visibility.observe(canvas);
    const onVisibility = () => schedule();
    document.addEventListener("visibilitychange", onVisibility);

    resize();
    // Start from the ball itself rather than random noise.
    const first = layout("sphere", 0, 0);
    particles.forEach((p, i) => {
      p.x = first[i].x;
      p.y = first[i].y;
    });
    // Start once the page has settled, so the particles don't compete with its first paint.
    const cancelStart = whenIdle(() => {
      running = true;
      schedule();
    });

    return () => {
      running = false;
      cancelStart();
      if (frame) cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      visibility.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reduced, ribbon, scrollProgress]);

  if (reduced) return null;
  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label="Animated points: a cricket ball, then every delivery in the data as a cloud, the 2019 IPL final's win-probability ribbon, and an illustration of simulated outcomes fanning out."
      className={className}
    />
  );
}
