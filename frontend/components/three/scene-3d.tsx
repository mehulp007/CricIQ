"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { Component, useEffect, useRef, useState, type ReactNode } from "react";

import type { SceneProps } from "@/components/three/stage";
import { useResolvedTheme } from "@/components/theme/use-resolved-theme";
import { can3D, readCapabilities } from "@/lib/three";
import { cn } from "@/lib/utils";

// Each scene, and three.js with it, is its own chunk: nothing 3D downloads until a scene is
// allowed and on screen.
const SCENES = {
  ball: dynamic(() => import("@/components/three/scenes/ball-scene"), { ssr: false }),
  bowled: dynamic(() => import("@/components/three/scenes/bowled-scene"), { ssr: false }),
  stadium: dynamic(() => import("@/components/three/scenes/stadium-scene"), { ssr: false }),
} satisfies Record<string, React.ComponentType<SceneProps>>;

export type SceneName = keyof typeof SCENES;

/** The events that show a visitor is on the page: any of them lets the 3D start. */
const FIRST_MOVES = ["pointermove", "pointerdown", "touchstart", "wheel", "scroll", "keydown"];

/** A scene that fails (a model that will not load, a lost WebGL context) leaves the poster. */
class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn("3D scene unavailable, showing its poster:", error);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/**
 * A 3D scene with its pre-rendered poster. The poster is what everyone sees first, and all that
 * visitors see who prefer reduced motion or saving data, whose browser has no WebGL, or whose
 * screen is narrower than `minWidth`. Otherwise the scene loads after the visitor's first move,
 * once on screen and the browser is idle, draws only while visible, and the poster fades out after
 * its first frame.
 */
export function Scene3D({
  scene,
  poster,
  width,
  height,
  label,
  minWidth = 0,
  priority = false,
  className,
}: {
  scene: SceneName;
  /** One poster, or one per theme for a scene lit by it (only the theme's own downloads). */
  poster: string | { dark: string; light: string };
  width: number;
  height: number;
  /** What the scene shows, for screen readers (the canvas itself is hidden from them). */
  label: string;
  minWidth?: number;
  priority?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [allowed, setAllowed] = useState(false);
  const [inView, setInView] = useState(false);
  const [pageVisible, setPageVisible] = useState(true);
  const [ready, setReady] = useState(false);
  const theme = useResolvedTheme();

  useEffect(() => {
    // Starting three.js takes the main thread for a moment, so it waits for the visitor's first
    // move (pointer, touch, wheel, scroll or key) and then for the browser to be idle: the page
    // loads and answers at full speed, and the poster (the scene's first frame) stands in till then.
    let idle: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const decide = () => setAllowed(can3D(readCapabilities(minWidth)));
    const start = () => {
      stop();
      if ("requestIdleCallback" in window)
        idle = window.requestIdleCallback(decide, { timeout: 1500 });
      else timer = setTimeout(decide, 100);
    };
    const stop = () => {
      for (const name of FIRST_MOVES) window.removeEventListener(name, start);
    };
    for (const name of FIRST_MOVES) window.addEventListener(name, start, { passive: true });
    return () => {
      stop();
      if (idle !== undefined) window.cancelIdleCallback(idle);
      clearTimeout(timer);
    };
  }, [minWidth]);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (!("IntersectionObserver" in window)) {
      const id = setTimeout(() => setInView(true), 0);
      return () => clearTimeout(id);
    }
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), {
      rootMargin: "120px",
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const onChange = () => setPageVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);

  const Scene = SCENES[scene];
  const posters: { src: string; theme?: "dark" | "light" }[] =
    typeof poster === "string"
      ? [{ src: poster }]
      : [
          { src: poster.dark, theme: "dark" },
          { src: poster.light, theme: "light" },
        ];
  // Once loaded, the scene stays mounted (paused when off screen) so scrolling back is instant.
  const mounted = allowed && (inView || ready);

  return (
    <div
      ref={ref}
      role="img"
      aria-label={label}
      data-scene={scene}
      data-scene-state={ready ? "3d" : "poster"}
      className={cn("relative", className)}
      style={{ aspectRatio: `${width} / ${height}` }}
    >
      {posters.map(({ src, theme: only }) => (
        <Image
          key={src}
          src={src}
          alt=""
          width={width}
          height={height}
          // A poster per theme loads lazily: the hidden one is never fetched.
          priority={priority && !only}
          className={cn(
            "pointer-events-none absolute inset-0 size-full object-contain transition-opacity duration-700 motion-reduce:transition-none",
            only === "dark" && "hidden dark:block",
            only === "light" && "dark:hidden",
            ready && "opacity-0",
          )}
        />
      ))}
      {mounted && (
        <div className="absolute inset-0">
          <SceneBoundary>
            <Scene active={inView && pageVisible} theme={theme} onReady={() => setReady(true)} />
          </SceneBoundary>
        </div>
      )}
    </div>
  );
}
