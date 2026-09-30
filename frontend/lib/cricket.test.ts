import { describe, expect, it } from "vitest";

import { formatRate, oversNotation, requiredRunRate, runRate } from "@/lib/cricket";

describe("oversNotation", () => {
  it.each([
    [0, "0.0"],
    [5, "0.5"],
    [6, "1.0"],
    [99, "16.3"],
    [120, "20.0"],
  ])("%i legal balls -> %s", (balls, expected) => {
    expect(oversNotation(balls)).toBe(expected);
  });

  it("rejects negative or fractional balls", () => {
    expect(() => oversNotation(-1)).toThrow(RangeError);
    expect(() => oversNotation(2.5)).toThrow(RangeError);
  });
});

describe("rates", () => {
  it("computes run rate per over", () => {
    expect(runRate(146, 99)).toBeCloseTo(8.848, 3);
    expect(runRate(0, 0)).toBeNull();
  });

  it("computes required run rate and edge cases", () => {
    expect(requiredRunRate(36, 18)).toBe(12);
    expect(requiredRunRate(0, 18)).toBeNull();
    expect(requiredRunRate(5, 0)).toBe(Infinity);
  });

  it("formats rates for display", () => {
    expect(formatRate(8.8484)).toBe("8.85");
    expect(formatRate(null)).toBe("—");
    expect(formatRate(Infinity)).toBe("∞");
  });
});
