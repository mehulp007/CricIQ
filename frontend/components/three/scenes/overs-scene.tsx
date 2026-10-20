"use client";

import { useGLTF } from "@react-three/drei";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef, type RefObject } from "react";
import {
  BoxGeometry,
  CanvasTexture,
  CylinderGeometry,
  MeshStandardMaterial,
  PerspectiveCamera,
  RepeatWrapping,
  SRGBColorSpace,
  type AmbientLight,
  type DirectionalLight,
  type Group,
  type HemisphereLight,
  type Mesh,
  type SpotLight,
} from "three";

import { Stage, type SceneProps } from "@/components/three/stage";
import type { OverBar } from "@/lib/replay/overs";
import type { Theme } from "@/lib/theme";

/** The colours the scene draws with, read from the theme's tokens (as rgb strings). */
export interface OversPalette {
  a: string;
  b: string;
  turf: string;
  turfStripe: string;
  chalk: string;
}

export interface OversSceneProps extends SceneProps {
  bars: OverBar[];
  /** Overs in an innings (20 or 50): the length of the ground. */
  overs: number;
  /** Pressure on the next ball, 0 to 100 (null between innings): the floodlights follow it. */
  pressure: number | null;
  palette: OversPalette;
  onSeek: (index: number) => void;
  onHover: (bar: OverBar | null) => void;
}

const STUMPS = "/3d/stumps.glb";
// The ground is the same length for every format (an over is a metre in a T20, 40 cm in an
// ODI), so bars read at the same scale; the side batting first behind, the chase in front.
const SPAN = 20;
const ROW_Z = { 1: -1.05, 2: 1.05 } as const;
const BAR = { width: 0.72, depth: 0.9 };
const PER_RUN = 0.13;
const MIN_HEIGHT = 0.05;
// The stumps model is 36 mm units, 20.3 tall with the bails: about 1 here.
const STUMPS_SCALE = 0.048;
const FALL = { angle: -1.3, seconds: 0.55 };
const DEPTH = 4.2;
// A long lens from high up: little perspective, so the chase does not hide the first innings.
const FOV = 24;
// A unit cube standing on its base, scaled to each bar's height.
const CUBE = new BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
const POLE = new CylinderGeometry(0.06, 0.09, 1, 8).translate(0, 0.5, 0);

// Night: the floodlights carry the scene and follow the pressure. Day: the sun does, and the
// floodlights only add to it.
const LOOK: Record<
  Theme,
  { ambient: number; sky: number; sun: number; flood: number; lamp: number }
> = {
  dark: { ambient: 0.22, sky: 0.3, sun: 0, flood: 2.6, lamp: 5 },
  light: { ambient: 0.6, sky: 1.0, sun: 2.0, flood: 0.8, lamp: 1.2 },
};

const slot = (overs: number) => SPAN / overs;
const xOf = (over: number, overs: number) => (over - (overs + 1) / 2) * slot(overs);
const heightOf = (bar: OverBar) => Math.max(bar.runs * PER_RUN, MIN_HEIGHT);

/** Mowing stripes, one per over, so the ground reads as a scale; they run on past the ends. */
function useTurf(overs: number, length: number, palette: OversPalette): CanvasTexture {
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = overs * 8;
    canvas.height = 8;
    const g = canvas.getContext("2d")!;
    for (let i = 0; i < overs; i++) {
      g.fillStyle = i % 2 ? palette.turfStripe : palette.turf;
      g.fillRect(i * 8, 0, 8, 8);
    }
    const texture = new CanvasTexture(canvas);
    texture.colorSpace = SRGBColorSpace;
    texture.wrapS = RepeatWrapping;
    // The ground is longer than the overs: line the stripes up with the bars.
    texture.repeat.x = length / SPAN;
    texture.offset.x = -(length - SPAN) / (2 * SPAN);
    return texture;
  }, [overs, length, palette]);
}

interface Clock {
  /** Wickets already down when the scene opens fall at once rather than all toppling together. */
  opened: number | null;
}

function Wicket({ x, z, clock }: { x: number; z: number; clock: RefObject<Clock> }) {
  const { scene } = useGLTF(STUMPS, false, true);
  const model = useMemo(() => scene.clone(true), [scene]);
  const pivot = useRef<Group>(null);
  const fell = useRef<number | null>(null);
  useFrame(({ clock: c }) => {
    if (!pivot.current) return;
    const now = c.elapsedTime;
    if (fell.current === null) {
      const opened = clock.current?.opened;
      fell.current =
        opened === null || opened === undefined || now - opened < 0.2 ? -Infinity : now;
    }
    const t = Math.min(1, (now - fell.current) / FALL.seconds);
    // Ease out, with a small bounce as the stumps hit the turf.
    const eased = t >= 1 ? 1 : 1 - Math.pow(1 - t, 3) + Math.sin(t * Math.PI) * 0.06;
    pivot.current.rotation.z = FALL.angle * eased;
  });
  return (
    <group ref={pivot} position={[x, 0, z]} scale={STUMPS_SCALE}>
      <primitive object={model} />
    </group>
  );
}

function Bar({
  bar,
  overs,
  material,
  clock,
  onSeek,
  onHover,
}: {
  bar: OverBar;
  overs: number;
  material: MeshStandardMaterial;
  clock: RefObject<Clock>;
  onSeek: (index: number) => void;
  onHover: (bar: OverBar | null) => void;
}) {
  const column = useRef<Mesh>(null);
  const top = useRef<Group>(null);
  const height = useRef<number | null>(null);
  const target = heightOf(bar);

  useFrame((_, delta) => {
    if (!column.current || !top.current) return;
    // A bar opened mid-replay starts at its height; one being bowled grows ball by ball.
    const h =
      height.current === null
        ? clock.current?.opened === null
          ? target
          : MIN_HEIGHT
        : height.current + (target - height.current) * Math.min(1, delta * 7);
    height.current = h;
    column.current.scale.y = h;
    top.current.position.y = h;
  });

  const hover = (event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation();
    document.body.style.cursor = "pointer";
    onHover(bar);
  };
  const leave = () => {
    document.body.style.cursor = "";
    onHover(null);
  };

  return (
    <group position={[xOf(bar.over, overs), 0, ROW_Z[bar.inningsNo]]}>
      <mesh
        ref={column}
        geometry={CUBE}
        material={material}
        scale={[BAR.width * slot(overs), MIN_HEIGHT, BAR.depth]}
        castShadow
        receiveShadow
        onPointerOver={hover}
        onPointerOut={leave}
        onClick={(event) => {
          event.stopPropagation();
          onSeek(bar.startIndex);
        }}
      />
      <group ref={top}>
        {Array.from({ length: bar.wickets }, (_, k) => (
          <Wicket
            key={k}
            x={(k - (bar.wickets - 1) / 2) * 0.22 * Math.min(1, slot(overs) * 1.5)}
            z={(k % 2 ? -1 : 1) * 0.12}
            clock={clock}
          />
        ))}
      </group>
    </group>
  );
}

function Tower({
  x,
  z,
  lamp,
}: {
  x: number;
  z: number;
  lamp: (material: MeshStandardMaterial | null) => void;
}) {
  // Lamp banks face the middle of the ground.
  const turn = Math.atan2(-x, -z);
  return (
    <group position={[x, 0, z]}>
      <mesh geometry={POLE} scale={[1, 4.6, 1]} castShadow>
        <meshStandardMaterial color="#8b939c" metalness={0.6} roughness={0.4} />
      </mesh>
      <mesh position={[0, 4.8, 0]} rotation={[0.45, turn, 0]}>
        <boxGeometry args={[1.4, 0.8, 0.14]} />
        <meshStandardMaterial ref={lamp} color="#eef2fb" emissive="#f6f8ff" roughness={0.3} />
      </mesh>
    </group>
  );
}

interface Rig {
  /** 1 at night, 0 by day, eased (-1 before the first frame). */
  night: number;
  /** 0 to 1, eased. */
  pressure: number;
}

function Overs({
  bars,
  overs,
  pressure,
  palette,
  theme,
  onSeek,
  onHover,
}: Omit<OversSceneProps, "active" | "onReady">) {
  const set = useThree((s) => s.set);
  const size = useThree((s) => s.size);
  const length = SPAN + 2.5;
  const turf = useTurf(overs, length, palette);
  const clock = useRef<Clock>({ opened: null });
  const rig = useRef<Rig>({ night: -1, pressure: 0.5 });
  const ambient = useRef<AmbientLight>(null);
  const sky = useRef<HemisphereLight>(null);
  const sun = useRef<DirectionalLight>(null);
  const floods = useRef<(SpotLight | null)[]>([]);
  const lamps = useRef<(MeshStandardMaterial | null)[]>([]);

  const towers = useMemo(
    () =>
      [-1, 1].flatMap((sx) =>
        [-1, 1].map((sz) => ({ x: sx * (length / 2 + 0.4), z: sz * (DEPTH / 2 + 0.6) })),
      ),
    [length],
  );

  const materials = useMemo(() => {
    const make = (color: string, emissive = 0) =>
      new MeshStandardMaterial({
        color,
        roughness: 0.45,
        metalness: 0.05,
        emissive: color,
        emissiveIntensity: emissive,
      });
    return {
      a: make(palette.a),
      b: make(palette.b),
      // The over being bowled glows a little.
      aNow: make(palette.a, 0.45),
      bNow: make(palette.b, 0.45),
    };
  }, [palette]);

  useLayoutEffect(() => {
    // Frame the whole ground: the camera stands back far enough for its width, raised so the
    // chase's bars do not hide the first innings'.
    const camera = new PerspectiveCamera(FOV, size.width / size.height, 0.5, 400);
    const half = Math.tan(((FOV / 2) * Math.PI) / 180) * camera.aspect;
    const distance = (length / 2 + 1) / half;
    camera.position.set(0, distance * 0.6, distance * 0.8);
    camera.lookAt(0, 0.9, 0);
    set({ camera });
  }, [length, set, size]);

  useFrame(({ clock: c }, delta) => {
    if (clock.current.opened === null) clock.current.opened = c.elapsedTime;
    const r = rig.current;
    const step = Math.min(1, Math.min(delta, 0.1) * 3);
    const goal = theme === "dark" ? 1 : 0;
    r.night = r.night < 0 ? goal : r.night + (goal - r.night) * step;
    r.pressure += ((pressure ?? 50) / 100 - r.pressure) * step;
    const mix = (key: keyof (typeof LOOK)["dark"]) =>
      LOOK.light[key] + (LOOK.dark[key] - LOOK.light[key]) * r.night;
    // The floodlights run from 35% at no pressure to full at the most.
    const flood = 0.35 + 0.65 * r.pressure;
    if (ambient.current) ambient.current.intensity = mix("ambient");
    if (sky.current) sky.current.intensity = mix("sky");
    if (sun.current) sun.current.intensity = mix("sun");
    for (const light of floods.current) if (light) light.intensity = mix("flood") * flood;
    for (const lamp of lamps.current) if (lamp) lamp.emissiveIntensity = mix("lamp") * flood;
  });

  return (
    <>
      <ambientLight ref={ambient} />
      <hemisphereLight ref={sky} args={["#dbe7ff", "#3d5a33"]} />
      <directionalLight
        ref={sun}
        position={[-length * 0.3, 18, 12]}
        color="#fff3df"
        castShadow={theme === "light"}
        shadow-mapSize={[2048, 1024]}
        shadow-camera-left={-length / 2 - 2}
        shadow-camera-right={length / 2 + 2}
        shadow-camera-top={8}
        shadow-camera-bottom={-8}
        shadow-camera-far={60}
        shadow-bias={-0.0004}
      />
      {towers.map((t, i) => (
        <spotLight
          key={i}
          ref={(light) => {
            floods.current[i] = light;
          }}
          position={[t.x, 4.9, t.z]}
          color="#f2f6ff"
          angle={0.9}
          penumbra={0.6}
          decay={0}
        />
      ))}
      {towers.map((t, i) => (
        <Tower
          key={i}
          x={t.x}
          z={t.z}
          lamp={(material) => {
            lamps.current[i] = material;
          }}
        />
      ))}

      {/* The ground: turf with a stripe per over, a chalk line between the innings. */}
      <mesh position={[0, -0.15, 0]} receiveShadow>
        <boxGeometry args={[length, 0.3, DEPTH]} />
        <meshStandardMaterial map={turf} roughness={0.95} />
      </mesh>
      <mesh position={[0, 0.005, 0]} rotation-x={-Math.PI / 2}>
        <planeGeometry args={[SPAN, 0.05]} />
        <meshBasicMaterial color={palette.chalk} />
      </mesh>

      {bars.map((bar) => (
        <Bar
          key={`${bar.inningsNo}-${bar.over}`}
          bar={bar}
          overs={overs}
          material={
            bar.inningsNo === 1
              ? bar.current
                ? materials.aNow
                : materials.a
              : bar.current
                ? materials.bNow
                : materials.b
          }
          clock={clock}
          onSeek={onSeek}
          onHover={onHover}
        />
      ))}
    </>
  );
}

/**
 * The over-by-over view in 3D: each over a bar on a strip of turf that rises as the replay plays,
 * stumps that fall on each wicket, and floodlights whose brightness follows the pressure on the
 * next ball. Clicking an over seeks the replay to it.
 */
export default function OversScene({ active, theme, onReady, ...props }: OversSceneProps) {
  return (
    <Stage active={active} theme={theme} onReady={onReady} shadows lights={false}>
      <Overs theme={theme} {...props} />
    </Stage>
  );
}
