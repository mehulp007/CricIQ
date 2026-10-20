"use client";

import { Environment, Lightformer } from "@react-three/drei";
import { Canvas, useFrame, type CameraProps } from "@react-three/fiber";
import { Suspense, useRef, type ReactNode } from "react";

import type { Theme } from "@/lib/theme";

/** Props every scene receives from Scene3D. */
export interface SceneProps {
  /** On screen and the tab visible: animate. Otherwise the canvas stops drawing. */
  active: boolean;
  theme: Theme;
  /** Called once the first frame with the models has been drawn, to hide the poster. */
  onReady: () => void;
}

// Floodlights at night (cool key, a turf-green rim), sunlight by day (warm key, softer rim).
const LIGHT = {
  dark: {
    ambient: 0.3,
    key: "#e6eeff",
    keyI: 2.4,
    rim: "#8be3bf",
    rimI: 1.6,
    fill: 0.45,
    env: 0.55,
  },
  light: {
    ambient: 0.55,
    key: "#fff2dc",
    keyI: 2.8,
    rim: "#ffffff",
    rimI: 0.9,
    fill: 0.7,
    env: 0.7,
  },
} as const;

function Lights({ theme }: { theme: Theme }) {
  const l = LIGHT[theme];
  return (
    <>
      <ambientLight intensity={l.ambient} />
      <directionalLight position={[4, 5, 4]} color={l.key} intensity={l.keyI} />
      <directionalLight position={[-5, 1, 2]} intensity={l.fill} />
      <directionalLight position={[-2, 3, -5]} color={l.rim} intensity={l.rimI} />
      {/* Soft reflections for the leather and varnish, rendered locally (no HDR download). */}
      <Environment resolution={128} frames={1} environmentIntensity={l.env}>
        <Lightformer form="rect" intensity={2} position={[4, 5, 4]} scale={[6, 4, 1]} />
        <Lightformer form="rect" intensity={1} position={[-5, 2, -3]} scale={[4, 6, 1]} />
        <Lightformer form="ring" intensity={0.6} position={[0, 6, -6]} scale={3} />
      </Environment>
    </>
  );
}

/** Calls onReady after the first frame that includes the (suspended) models. */
function Ready({ onReady }: { onReady: () => void }) {
  const done = useRef(false);
  useFrame(() => {
    if (done.current) return;
    done.current = true;
    requestAnimationFrame(onReady);
  });
  return null;
}

/** The canvas every scene shares: capped pixel ratio, transparent, drawing only while active. */
export function Stage({
  active,
  theme,
  onReady,
  camera,
  shadows = false,
  lights = true,
  children,
}: SceneProps & {
  camera?: CameraProps;
  shadows?: boolean;
  /** The shared lights; a scene that lights itself turns them off. */
  lights?: boolean;
  children: ReactNode;
}) {
  return (
    <Canvas
      shadows={shadows}
      frameloop={active ? "always" : "never"}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      camera={camera}
      aria-hidden="true"
    >
      {lights && <Lights theme={theme} />}
      <Suspense fallback={null}>
        {children}
        <Ready onReady={onReady} />
      </Suspense>
    </Canvas>
  );
}
