import { describe, expect, it } from "vitest";

import final2019 from "@/data/featured/1181768.json";
import type { Timeline } from "@/lib/api/types";

import {
  probabilityAtLeast,
  projectionAt,
  projectionCone,
  thresholdsFor,
  type Projection,
} from "./projection";

const final = final2019 as unknown as Timeline;
const chaseStart = final.deliveries.findIndex((d) => d.innings_no === 2);

const sample: Projection = {
  quantiles: [150, 155, 162, 170, 178, 185, 190],
  levels: [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95],
  current: 120,
  median: 170,
  low: 155,
  high: 185,
};

describe("projectionAt", () => {
  it("covers the first innings only", () => {
    const start = projectionAt(final, -1)!;
    expect(start.current).toBe(0);
    expect(start.low).toBeLessThan(start.median);
    expect(start.median).toBeLessThan(start.high);
    const mid = projectionAt(final, 60)!;
    expect(mid.quantiles[0]).toBeGreaterThanOrEqual(mid.current);
    // After the last ball of the innings the total is known; chases are not projected.
    expect(projectionAt(final, chaseStart - 1)).toBeNull();
    expect(projectionAt(final, chaseStart + 10)).toBeNull();
  });

  it("closes in on the real total (149) as the innings goes on", () => {
    const early = projectionAt(final, 5)!;
    const late = projectionAt(final, chaseStart - 6)!;
    expect(late.high - late.low).toBeLessThan(early.high - early.low);
    expect(Math.abs(late.median - 149)).toBeLessThan(15);
  });
});

describe("probabilityAtLeast", () => {
  it("matches the quantiles and never increases with the threshold", () => {
    expect(probabilityAtLeast(sample, 100)).toBe(1);
    expect(probabilityAtLeast(sample, 170)).toBeCloseTo(0.5);
    expect(probabilityAtLeast(sample, 155)).toBeCloseTo(0.9);
    expect(probabilityAtLeast(sample, 300)).toBe(0);
    const probs = [130, 150, 160, 170, 180, 190, 200].map((t) => probabilityAtLeast(sample, t));
    probs.slice(1).forEach((p, i) => expect(p).toBeLessThanOrEqual(probs[i]));
  });

  it("picks round thresholds around the projection", () => {
    expect(thresholdsFor(sample)).toEqual([150, 160, 180, 190]);
    expect(thresholdsFor({ ...sample, current: 165 })).toEqual([180, 190]);
  });
});

describe("projectionCone", () => {
  it("fans out from the current score to the end of the innings", () => {
    const cone = projectionCone(final, 30);
    expect(cone).toHaveLength(2);
    expect(cone[0].band[0]).toBe(cone[0].band[1]);
    expect(cone[1].x).toBe(20);
    expect(cone[1].band[0]).toBeLessThan(cone[1].band[1]);
    expect(projectionCone(final, chaseStart + 1)).toEqual([]);
  });
});
