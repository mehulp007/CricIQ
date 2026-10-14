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
} satisfies Record<string, React.ComponentType<SceneProps>>;

export type SceneName = keyof typeof SCENES;

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
 * screen is narrower than `minWidth`. Otherwise the scene loads once on screen and the browser is
 * idle, draws only while visible, and the poster fades out after its first frame.
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
  poster: string;
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
    const decide = () => setAllowed(can3D(readCapabilities(minWidth)));
    // After the page has settled, so the 3D never competes with the first paint.
    if ("requestIdleCallback" in window) {
      const id = window.requestIdleCallback(decide, { timeout: 2500 });
      return () => window.cancelIdleCallback(id);
    }
    const id = setTimeout(decide, 300);
    return () => clearTimeout(id);
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
      <Image
        src={poster}
        alt=""
        width={width}
        height={height}
        priority={priority}
        className={cn(
          "pointer-events-none absolute inset-0 size-full object-contain transition-opacity duration-700 motion-reduce:transition-none",
          ready && "opacity-0",
        )}
      />
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
