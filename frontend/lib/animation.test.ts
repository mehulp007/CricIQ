import { afterEach, describe, expect, it, vi } from "vitest";

import { clamp, lerp, mapRange, prefersReducedMotion, whenIdle } from "@/lib/animation";

describe("clamp and lerp", () => {
  it("clamps to the range", () => {
    expect(clamp(5, 0, 1)).toBe(1);
    expect(clamp(-5, 0, 1)).toBe(0);
    expect(clamp(0.4, 0, 1)).toBe(0.4);
  });

  it("interpolates linearly", () => {
    expect(lerp(10, 20, 0)).toBe(10);
    expect(lerp(10, 20, 0.25)).toBe(12.5);
    expect(lerp(10, 20, 1)).toBe(20);
  });
});

describe("mapRange", () => {
  it("maps a window of scroll progress onto an output range", () => {
    expect(mapRange(0.5, 0.25, 0.75, 0, 100)).toBe(50);
    expect(mapRange(0.3, 0.2, 0.4, 1, 0)).toBeCloseTo(0.5);
  });

  it("holds the ends outside the window", () => {
    expect(mapRange(0, 0.25, 0.75, 0, 100)).toBe(0);
    expect(mapRange(1, 0.25, 0.75, 0, 100)).toBe(100);
  });
});

describe("whenIdle", () => {
  afterEach(() => vi.useRealTimers());

  it("runs the callback later, unless cancelled", () => {
    vi.useFakeTimers();
    const ran = vi.fn();
    whenIdle(ran);
    const cancelled = vi.fn();
    whenIdle(cancelled)();
    expect(ran).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(ran).toHaveBeenCalledOnce();
    expect(cancelled).not.toHaveBeenCalled();
  });
});

describe("prefersReducedMotion", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads the media query", () => {
    const matchMedia = vi.fn((query: string) => ({ matches: query.includes("reduce") }));
    vi.stubGlobal("matchMedia", matchMedia);
    expect(prefersReducedMotion()).toBe(true);
    expect(matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");
  });
});
