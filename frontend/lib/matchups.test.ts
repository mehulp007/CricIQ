import { describe, expect, it } from "vitest";

import {
  METRICS,
  axisFor,
  formatValue,
  parsePhase,
  parsePlayerId,
  percent,
  position,
  weightSentence,
} from "./matchups";

describe("matchup helpers", () => {
  it("parses url params defensively", () => {
    expect(parsePhase("death")).toBe("death");
    expect(parsePhase(["middle"])).toBe("middle");
    expect(parsePhase("tea")).toBeUndefined();
    expect(parsePlayerId("ba607b88")).toBe("ba607b88");
    expect(parsePlayerId("../etc")).toBeUndefined();
    expect(parsePlayerId(undefined)).toBeUndefined();
  });

  it("builds a padded axis that never goes below zero", () => {
    const [lo, hi] = axisFor([
      { value: 120, low: 90, high: 150 },
      { value: 130, low: 125, high: 135 },
      null,
    ]);
    expect(lo).toBeLessThan(90);
    expect(lo).toBeGreaterThanOrEqual(0);
    expect(hi).toBeGreaterThan(150);
    expect(axisFor([{ value: 2, low: 0, high: 5 }])[0]).toBe(0);
    expect(axisFor([])).toEqual([0, 1]);
  });

  it("positions values on the axis", () => {
    expect(position(50, [0, 100])).toBe(50);
    expect(position(-10, [0, 100])).toBe(0);
    expect(position(500, [0, 100])).toBe(100);
    expect(position(1, [1, 1])).toBe(50);
  });

  it("formats values", () => {
    expect(formatValue(131.42, METRICS[0])).toBe("131.4");
    expect(formatValue(null, METRICS[0])).toBe("—");
    expect(formatValue(38.2, METRICS[2])).toBe("38.2%");
    expect(percent(0.0452)).toBe("4.5%");
  });

  it("explains the weight of history", () => {
    expect(weightSentence(0.12, 400)).toContain("12%");
    expect(weightSentence(0.12, 400)).toContain("400 balls");
  });
});
