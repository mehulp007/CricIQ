"use client";

import { useGLTF } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useLayoutEffect, useRef } from "react";
import { Mesh, PerspectiveCamera, Vector3 } from "three";

import { Stage, type SceneProps } from "@/components/three/stage";
import { fromBlenderPosition } from "@/lib/three";

const MODEL = "/3d/bowled.glb";
// What the Blender camera looks at (assets-src/3d/bowled.blend): the camera drifts around it.
const TARGET = new Vector3(...fromBlenderPosition([0.6, 0.8, 8.5]));
const UP = new Vector3(0, 1, 0);
// A floodlight high behind and to the left casts the shadows, falling forward and right as in
// the poster.
const KEY = fromBlenderPosition([-18, 30, 60]);

interface Rig {
  camera: PerspectiveCamera;
  offset: Vector3;
}

function Bowled() {
  const gltf = useGLTF(MODEL, false, true);
  const set = useThree((s) => s.set);
  const size = useThree((s) => s.size);
  const rig = useRef<Rig | null>(null);

  useLayoutEffect(() => {
    // The scene's own camera (exported from Blender with the poster's framing), copied out of
    // the model so it can move while the stumps stay put.
    const source = gltf.cameras[0] as PerspectiveCamera;
    source.updateWorldMatrix(true, false);
    const camera = new PerspectiveCamera(source.fov, size.width / size.height, 0.1, 400);
    source.getWorldPosition(camera.position);
    source.getWorldQuaternion(camera.quaternion);
    rig.current = { camera, offset: camera.position.clone().sub(TARGET) };
    set({ camera });
  }, [gltf, set, size]);

  useLayoutEffect(() => {
    gltf.scene.traverse((o) => {
      if (o instanceof Mesh) o.castShadow = true;
    });
  }, [gltf]);

  useFrame(({ clock }) => {
    if (!rig.current) return;
    // A slow drift of a few degrees either side of the poster's view.
    const { camera, offset } = rig.current;
    const angle = Math.sin(clock.elapsedTime * 0.25) * 0.06;
    camera.position.copy(TARGET).add(offset.clone().applyAxisAngle(UP, angle));
    camera.lookAt(TARGET);
  });

  return (
    <>
      <directionalLight
        position={KEY}
        intensity={1.2}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
        shadow-radius={6}
        shadow-camera-left={-30}
        shadow-camera-right={30}
        shadow-camera-top={30}
        shadow-camera-bottom={-30}
        shadow-camera-near={1}
        shadow-camera-far={140}
      />
      <primitive object={gltf.scene} />
      {/* The ground shows only the shadows falling on it. */}
      <mesh rotation-x={-Math.PI / 2} receiveShadow>
        <planeGeometry args={[160, 160]} />
        <shadowMaterial opacity={0.3} />
      </mesh>
    </>
  );
}

/** Stumps broken: the off stump knocked back, the bails on the ground, the ball at rest. */
export default function BowledScene(props: SceneProps) {
  return (
    <Stage {...props} shadows>
      <Bowled />
    </Stage>
  );
}
