"use client";

import { Environment, Lightformer, useGLTF } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef } from "react";
import {
  AdditiveBlending,
  CanvasTexture,
  DirectionalLight,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  SpotLight,
  Sprite,
  Vector3,
  type AmbientLight,
  type Group,
  type HemisphereLight,
} from "three";

import { Stage, type SceneProps } from "@/components/three/stage";
import { fromBlenderPosition } from "@/lib/three";
import type { Theme } from "@/lib/theme";

const MODEL = "/3d/stadium.glb";
const ORIGIN = new Vector3();
// The ground turns once in about three minutes, under a camera and a sun that stay put, so the
// side facing the viewer is always the lit one (as in the posters).
const TURN = (2 * Math.PI) / 180;
const LAMPS = ["Floodlamps0", "Floodlamps1", "Floodlamps2", "Floodlamps3"];

// Night: the floodlights on, the lamps and the ribbon glowing. Day: sunshine, the lamps off.
const LOOK: Record<
  Theme,
  {
    ambient: number;
    sky: number;
    sun: number;
    spot: number;
    lamp: number;
    ribbon: number;
    glare: number;
  }
> = {
  dark: { ambient: 0.12, sky: 0.25, sun: 0, spot: 2.1, lamp: 6, ribbon: 2.6, glare: 1 },
  light: { ambient: 0.7, sky: 1.3, sun: 2.8, spot: 0, lamp: 0, ribbon: 0, glare: 0 },
};

/** A soft round glow, drawn once, for the glare around each lamp bank at night. */
function useGlareTexture(): CanvasTexture {
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 128;
    const g = canvas.getContext("2d")!;
    const gradient = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.18, "rgba(240,245,255,0.75)");
    gradient.addColorStop(0.5, "rgba(220,230,255,0.18)");
    gradient.addColorStop(1, "rgba(220,230,255,0)");
    g.fillStyle = gradient;
    g.fillRect(0, 0, 128, 128);
    return new CanvasTexture(canvas);
  }, []);
}

interface Rig {
  /** 1 at night, 0 by day: eased towards the theme so a switch fades rather than snaps
   * (-1 until the first frame, which starts at the theme). */
  night: number;
  lamp: MeshStandardMaterial | null;
  ribbon: MeshStandardMaterial | null;
}

function Stadium({ theme }: { theme: Theme }) {
  const gltf = useGLTF(MODEL, false, true);
  const set = useThree((s) => s.set);
  const size = useThree((s) => s.size);
  const glare = useGlareTexture();
  const rig = useRef<Rig | null>(null);
  const turntable = useRef<Group>(null);
  const ambient = useRef<AmbientLight>(null);
  const sky = useRef<HemisphereLight>(null);
  const sun = useRef<DirectionalLight>(null);
  const spots = useRef<(SpotLight | null)[]>([]);
  const glares = useRef<(Sprite | null)[]>([]);

  // Where each lamp bank is and where it points (at the middle of the ground).
  const lamps = useMemo(
    () =>
      LAMPS.map((name) => {
        // Every node sits at the top of the model, so its position is where it is in the world.
        const position = gltf.nodes[name]?.position.clone() ?? new Vector3();
        const aim = ORIGIN.clone().sub(position).normalize();
        return { position, glare: position.clone().addScaledVector(aim, 3) };
      }),
    [gltf],
  );

  useLayoutEffect(() => {
    // The scene's own camera, with the posters' framing.
    const source = gltf.cameras[0] as PerspectiveCamera;
    source.updateWorldMatrix(true, false);
    const camera = new PerspectiveCamera(source.fov, size.width / size.height, 1, 2000);
    source.getWorldPosition(camera.position);
    source.getWorldQuaternion(camera.quaternion);
    rig.current = {
      night: rig.current?.night ?? -1,
      lamp: (gltf.materials.Floodlamp as MeshStandardMaterial | undefined) ?? null,
      ribbon: (gltf.materials.Ribbon as MeshStandardMaterial | undefined) ?? null,
    };
    set({ camera });
  }, [gltf, set, size]);

  useLayoutEffect(() => {
    gltf.scene.traverse((o) => {
      if (o instanceof Mesh) {
        o.castShadow = true;
        o.receiveShadow = true;
      }
    });
  }, [gltf]);

  useFrame((_, delta) => {
    const r = rig.current;
    if (!r) return;
    const step = Math.min(delta, 0.1);
    if (turntable.current) turntable.current.rotation.y -= step * TURN;

    const goal = theme === "dark" ? 1 : 0;
    r.night = r.night < 0 ? goal : r.night + (goal - r.night) * Math.min(1, step * 3);
    const mix = (key: keyof (typeof LOOK)["dark"]) =>
      LOOK.light[key] + (LOOK.dark[key] - LOOK.light[key]) * r.night;
    if (ambient.current) ambient.current.intensity = mix("ambient");
    if (sky.current) sky.current.intensity = mix("sky");
    if (sun.current) sun.current.intensity = mix("sun");
    for (const spot of spots.current) if (spot) spot.intensity = mix("spot");
    for (const sprite of glares.current) if (sprite) sprite.material.opacity = mix("glare");
    if (r.lamp) r.lamp.emissiveIntensity = mix("lamp");
    if (r.ribbon) r.ribbon.emissiveIntensity = mix("ribbon");
  });

  return (
    <>
      <ambientLight ref={ambient} />
      <hemisphereLight ref={sky} args={["#cfe3ff", "#4a5a3c"]} />
      {/* The sun, high behind the camera, and the only shadows (by day). */}
      <directionalLight
        ref={sun}
        position={fromBlenderPosition([30, -170, 150])}
        color="#fff3df"
        castShadow={theme === "light"}
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0005}
        shadow-camera-left={-150}
        shadow-camera-right={150}
        shadow-camera-top={150}
        shadow-camera-bottom={-150}
        shadow-camera-near={10}
        shadow-camera-far={600}
      />
      <group ref={turntable}>
        <primitive object={gltf.scene} />
        {/* The floodlights turn with their towers. */}
        {lamps.map((lamp, i) => (
          <spotLight
            key={LAMPS[i]}
            ref={(light) => {
              spots.current[i] = light;
            }}
            position={lamp.position}
            color="#f2f6ff"
            angle={0.8}
            penumbra={0.7}
            decay={0}
          />
        ))}
        {lamps.map((lamp, i) => (
          <sprite
            key={`glare-${LAMPS[i]}`}
            ref={(sprite) => {
              glares.current[i] = sprite;
            }}
            position={lamp.glare}
            scale={34}
          >
            <spriteMaterial
              map={glare}
              blending={AdditiveBlending}
              transparent
              depthWrite={false}
              opacity={0}
            />
          </sprite>
        ))}
      </group>
      <Environment resolution={64} frames={1} environmentIntensity={theme === "dark" ? 0.3 : 0.7}>
        <Lightformer form="rect" intensity={2} position={[60, 80, 60]} scale={[80, 60, 1]} />
        <Lightformer form="rect" intensity={1} position={[-80, 40, -40]} scale={[60, 80, 1]} />
      </Environment>
    </>
  );
}

/** A floodlit stadium, turning slowly: lit by floodlights at night and the sun by day. */
export default function StadiumScene(props: SceneProps) {
  return (
    <Stage {...props} shadows lights={false}>
      <Stadium theme={props.theme} />
    </Stage>
  );
}
