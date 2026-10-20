"use client";

import { RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { usePrefersReducedMotion } from "@/lib/animation";

const W = 320;
const H = 200;
const GROUND = 176;
const STUMP_X = [196, 212, 228];
const STUMP_TOP = 82;
const STUMP_W = 6;
const HIT_AT = 0.62; // seconds: when the ball reaches the stumps

interface Piece {
  x: number;
  y: number;
  vx: number;
  vy: number;
  angle: number;
  spin: number;
  w: number;
  h: number;
  life: number;
  kind: "bail" | "chip";
}

/** A stable pseudo-random number for a seed (so the scene plays the same every time). */
function rand(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

/** A colour the canvas understands, from a theme variable (falling back when it can't parse it). */
function themeColor(ctx: CanvasRenderingContext2D, name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  ctx.fillStyle = fallback;
  if (value) ctx.fillStyle = value;
  return String(ctx.fillStyle);
}

/**
 * The 404's small scene, drawn on a canvas: a ball pitches and crashes into the stumps, the bails
 * fly off and splinters scatter, then settle on the ground. It plays once (and again on request);
 * with reduced motion the page shows its words alone.
 */
export function Bowled() {
  const reduced = usePrefersReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [take, setTake] = useState(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (reduced || !canvas || !ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const ink = themeColor(ctx, "--foreground", "#e6ebf2");
    const turf = themeColor(ctx, "--primary", "#3fd08b");
    const ball = themeColor(ctx, "--wicket", "#e5534b");
    const spark = themeColor(ctx, "--team-b", "#f2b544");

    const pieces: Piece[] = [];
    let hit = false;
    let start = 0;
    let frame = 0;

    function burst() {
      // The two bails, thrown up and back off the top of the stumps.
      [0, 1].forEach((i) => {
        pieces.push({
          x: STUMP_X[i] + 6,
          y: STUMP_TOP - 3,
          vx: 70 + i * 55,
          vy: -230 - i * 40,
          angle: 0,
          spin: (i ? 1 : -1) * (9 + i * 4),
          w: 13,
          h: 4,
          life: Infinity,
          kind: "bail",
        });
      });
      // Splinters and dust from where the ball struck.
      for (let i = 0; i < 26; i++) {
        const a = -Math.PI * (0.15 + 0.7 * rand(i + 1));
        const speed = 90 + 220 * rand(i + 40);
        pieces.push({
          x: STUMP_X[1],
          y: 140 + 20 * rand(i + 80),
          vx: Math.cos(a) * speed * (rand(i + 7) > 0.25 ? 1 : -0.6),
          vy: Math.sin(a) * speed,
          angle: rand(i + 3) * Math.PI,
          spin: (rand(i + 9) - 0.5) * 20,
          w: 2 + 3 * rand(i + 11),
          h: 2,
          life: 0.7 + 0.8 * rand(i + 13),
          kind: "chip",
        });
      }
    }

    function draw(now: number) {
      if (!start) start = now;
      const t = (now - start) / 1000;
      ctx!.clearRect(0, 0, W, H);

      // The pitch.
      ctx!.fillStyle = turf;
      ctx!.globalAlpha = 0.35;
      ctx!.fillRect(0, GROUND, W, 2);
      ctx!.globalAlpha = 1;

      // The stumps: the middle one knocked back once struck.
      const knock = hit ? Math.min((t - HIT_AT) * 4, 1) : 0;
      STUMP_X.forEach((x, i) => {
        ctx!.save();
        ctx!.translate(x + STUMP_W / 2, GROUND);
        ctx!.rotate((i === 1 ? 0.32 : i === 2 ? 0.12 : 0.05) * knock);
        ctx!.fillStyle = ink;
        ctx!.globalAlpha = 0.9;
        ctx!.fillRect(-STUMP_W / 2, STUMP_TOP - GROUND, STUMP_W, GROUND - STUMP_TOP);
        ctx!.restore();
      });

      // The bails on top until the ball arrives.
      if (!hit) {
        ctx!.fillStyle = ink;
        ctx!.fillRect(STUMP_X[0], STUMP_TOP - 4, 13, 4);
        ctx!.fillRect(STUMP_X[1] + 1, STUMP_TOP - 4, 13, 4);
      }

      // The ball: in from the left, pitching on a good length, then into the stumps.
      if (t < HIT_AT + 0.05) {
        const p = Math.min(t / HIT_AT, 1);
        const x = -20 + (STUMP_X[0] + 2 + 20) * p;
        const pitch = 0.62;
        const y =
          p < pitch
            ? 70 + (GROUND - 6 - 70) * (p / pitch) ** 2
            : GROUND -
              6 -
              (GROUND - 6 - 150) * Math.sin(((p - pitch) / (1 - pitch)) * (Math.PI / 2));
        ctx!.fillStyle = ball;
        ctx!.beginPath();
        ctx!.arc(x, y, 6, 0, Math.PI * 2);
        ctx!.fill();
      }
      if (!hit && t >= HIT_AT) {
        hit = true;
        burst();
      }

      // Flying bails and splinters, falling and coming to rest on the ground.
      const dt = 1 / 60;
      for (const piece of pieces) {
        piece.vy += 620 * dt;
        piece.x += piece.vx * dt;
        piece.y += piece.vy * dt;
        piece.angle += piece.spin * dt;
        if (piece.y > GROUND - piece.h / 2) {
          piece.y = GROUND - piece.h / 2;
          piece.vy *= -0.3;
          piece.vx *= 0.6;
          piece.spin *= 0.5;
        }
        if (piece.kind === "chip") piece.life -= dt;
        if (piece.life <= 0) continue;
        ctx!.save();
        ctx!.translate(piece.x, piece.y);
        ctx!.rotate(piece.angle);
        ctx!.globalAlpha = piece.kind === "chip" ? Math.min(piece.life, 1) * 0.9 : 1;
        ctx!.fillStyle = piece.kind === "bail" ? ink : spark;
        ctx!.fillRect(-piece.w / 2, -piece.h / 2, piece.w, piece.h);
        ctx!.restore();
      }
      ctx!.globalAlpha = 1;

      if (t < 3.2) frame = requestAnimationFrame(draw);
    }
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [reduced, take]);

  if (reduced) return null;
  return (
    <div className="flex flex-col items-start gap-2">
      <canvas
        ref={canvasRef}
        role="img"
        aria-label="A ball hits the stumps and the bails fly off."
        style={{ width: W, height: H }}
        className="max-w-full"
      />
      <button
        type="button"
        onClick={() => setTake((n) => n + 1)}
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        <RotateCcw className="size-3.5" aria-hidden="true" />
        Bowl it again
      </button>
    </div>
  );
}
