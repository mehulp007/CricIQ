"use client";

import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import type { Group } from "three";

import { Stage, type SceneProps } from "@/components/three/stage";
import { fromBlenderPosition, fromBlenderQuaternion, verticalFov } from "@/lib/three";

const MODEL = "/3d/cricket-ball.glb";
// The camera and the ball's starting turn are those of the poster's Blender scene
// (assets-src/3d/bowled.blend, scene "Hero"), so the 3D ball takes over without a jump.
const CAMERA = {
  position: fromBlenderPosition([3.6, -6.2, 2.4]),
  fov: verticalFov(85, 1),
  near: 0.1,
  far: 100,
};
const START = fromBlenderQuaternion([0.885345, -0.06786, 0.459956, 0]);

function Ball() {
  const { scene } = useGLTF(MODEL, false, true);
  const model = useMemo(() => scene.clone(true), [scene]);
  const spin = useRef<Group>(null);
  useFrame((_, delta) => {
    if (spin.current) spin.current.rotation.y += delta * 0.35;
  });
  return (
    <group ref={spin}>
      <group quaternion={START}>
        <primitive object={model} />
      </group>
    </group>
  );
}

/** A cricket ball turning slowly. */
export default function BallScene(props: SceneProps) {
  return (
    <Stage {...props} camera={CAMERA}>
      <Ball />
    </Stage>
  );
}
