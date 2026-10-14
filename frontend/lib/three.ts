/**
 * When a 3D scene may load. Every scene has a pre-rendered poster; the 3D version replaces it only
 * when it can run well and the visitor has not asked for less motion or data.
 */

export interface Capabilities {
  reducedMotion: boolean;
  saveData: boolean;
  webgl: boolean;
  /** The viewport is at least the scene's minimum width (scenes that only show on larger screens). */
  wideEnough: boolean;
}

export function can3D(c: Capabilities): boolean {
  return c.webgl && c.wideEnough && !c.reducedMotion && !c.saveData;
}

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/** Read the browser's capabilities (client only). */
export function readCapabilities(minWidth = 0): Capabilities {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  return {
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    saveData: Boolean(connection?.saveData),
    webgl: hasWebGL(),
    wideEnough: minWidth === 0 || window.matchMedia(`(min-width: ${minWidth}px)`).matches,
  };
}

/** Blender is Z-up and glTF/three.js Y-up: a Blender position (x, y, z) is (x, z, -y) here. */
export function fromBlenderPosition([x, y, z]: [number, number, number]): [number, number, number] {
  return [x, z, -y];
}

/** A Blender quaternion (w, x, y, z) as a three.js one (x, y, z, w) in Y-up space. */
export function fromBlenderQuaternion([w, x, y, z]: [number, number, number, number]): [
  number,
  number,
  number,
  number,
] {
  return [x, z, -y, w];
}

/** Vertical field of view (degrees) of a Blender camera with a 36 mm sensor fitted to the width. */
export function verticalFov(lensMm: number, aspect: number): number {
  const horizontal = 2 * Math.atan(18 / lensMm);
  return (2 * Math.atan(Math.tan(horizontal / 2) / aspect) * 180) / Math.PI;
}
