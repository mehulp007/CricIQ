/**
 * Animation constants and utilities shared across the landing and app pages.
 * All animations respect prefers-reduced-motion.
 */
import { useSyncExternalStore } from "react";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

/**
 * Whether the visitor has moved between pages yet (set by app/template.tsx once the first page has
 * mounted). The first page of a visit is hydrated from the server's HTML, so anything on screen
 * stays as rendered; on later pages, rendered in the browser, things may start hidden and enter.
 */
export const visit = { navigated: false };

const noSubscription = () => () => {};

/**
 * Whether this component is being hydrated from the server's HTML (what the visitor already sees)
 * rather than rendered in the browser. React reads the server snapshot while hydrating and the
 * client one otherwise, so this holds for each component, even ones streamed in late.
 */
export function useIsHydrating(): boolean {
  return useSyncExternalStore(
    noSubscription,
    () => false,
    () => true,
  );
}

/** Whether the visitor prefers reduced motion. Checked once on load. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia(REDUCED_MOTION).matches;
}

function subscribeReducedMotion(onChange: () => void): () => void {
  const media = window.matchMedia(REDUCED_MOTION);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

/**
 * The reduced-motion preference in a component, kept up to date. The server (and hydration) render
 * with motion; CSS `motion-reduce:` variants cover the first paint, so nothing flashes.
 */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReducedMotion, prefersReducedMotion, () => false);
}

/**
 * Run `callback` once the browser is idle (at the latest after `timeout` ms), so decorative work
 * doesn't compete with the first paint. Returns a function that cancels it.
 */
export function whenIdle(callback: () => void, timeout = 1200): () => void {
  if (typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(callback, { timeout });
    return () => window.cancelIdleCallback(id);
  }
  const id = setTimeout(callback, 300);
  return () => clearTimeout(id);
}

/**
 * Resolves once the page has loaded and the browser is idle: a lazy import that waits for it stays
 * off the path to the page's first paint, however quickly the page hydrates.
 */
export function afterLoad(): Promise<void> {
  return new Promise((resolve) => {
    const idle = () => whenIdle(resolve, 1500);
    if (document.readyState === "complete") idle();
    else window.addEventListener("load", idle, { once: true });
  });
}

/**
 * Resolves in a fresh task, so the browser can paint and handle input in between: long set-up work
 * awaits it between steps instead of holding the main thread in one block.
 */
export function nextTask(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
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
