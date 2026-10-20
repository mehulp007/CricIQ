"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { useRef, useState } from "react";

import type { SceneProps } from "@/components/three/stage";
import { SceneBoundary, use3DAllowed, useInView, usePageVisible } from "@/components/three/use-3d";
import { useResolvedTheme } from "@/components/theme/use-resolved-theme";
import { cn } from "@/lib/utils";

// Each scene, and three.js with it, is its own chunk: nothing 3D downloads until a scene is
// allowed and on screen.
const SCENES = {
  ball: dynamic(() => import("@/components/three/scenes/ball-scene"), { ssr: false }),
  bowled: dynamic(() => import("@/components/three/scenes/bowled-scene"), { ssr: false }),
  stadium: dynamic(() => import("@/components/three/scenes/stadium-scene"), { ssr: false }),
} satisfies Record<string, React.ComponentType<SceneProps>>;

export type SceneName = keyof typeof SCENES;

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
  const allowed = use3DAllowed(minWidth);
  const inView = useInView(ref);
  const pageVisible = usePageVisible();
  const [ready, setReady] = useState(false);
  const theme = useResolvedTheme();

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
