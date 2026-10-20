/**
 * Animation constants and utilities shared across the landing and app pages.
 * All animations respect prefers-reduced-motion.
 */

/** Whether the visitor prefers reduced motion. Checked once on load. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Clamp a value between min and max. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** Linear interpolation. */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Map a scroll progress (0–1) to an output range. */
export function mapRange(
  progress: number,
  inMin: number,
  inMax: number,
  outMin: number,
  outMax: number,
): number {
  const t = clamp((progress - inMin) / (inMax - inMin), 0, 1);
  return lerp(outMin, outMax, t);
}
