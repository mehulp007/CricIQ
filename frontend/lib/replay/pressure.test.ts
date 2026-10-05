import { describe, expect, it } from "vitest";

import type { Timeline } from "@/lib/api/types";

import {
  formatLeverage,
  momentumAt,
  pressureAt,
  pressureBand,
  pressurePeaks,
  pressureSeries,
} from "./pressure";

function delivery(
  innings_no: number,
  seq_no: number,
  over_no: number,
  extra: Partial<Timeline["deliveries"][number]> = {},
) {
  return {
    innings_no,
    seq_no,
    over_no,
    ball_label: `${over_no}.${seq_no}`,
    legal_ball_no: seq_no,
    team_runs: seq_no,
    team_wickets: 0,
    ...extra,
  };
}

const timeline = {
  innings: [
    { innings_no: 1, pressure_start: 40, leverage_start: 0.7, max_balls: 120 },
    { innings_no: 2, pressure_start: 55, leverage_start: 0.9, target_runs: 150, max_balls: 120 },
  ],
  deliveries: [
    delivery(1, 1, 0, { pressure: 30, leverage: 0.6, momentum: 1.2 }),
    delivery(1, 2, 0, { pressure: null, leverage: null, momentum: -3.4 }),
    delivery(2, 1, 0, { pressure: 97, leverage: 3.1, momentum: 0 }),
    delivery(2, 2, 0, { pressure: 99, leverage: 12.4, momentum: 8 }),
    delivery(2, 3, 1, { pressure: 90, leverage: 1.9, momentum: 9 }),
    delivery(2, 4, 1, { pressure: null, leverage: null, momentum: 30 }),
  ],
} as unknown as Timeline;

describe("pressure", () => {
  it("bands the index", () => {
    expect([0, 49, 50, 79, 80, 94, 95, 100].map(pressureBand)).toEqual([
      "Low",
      "Low",
      "Medium",
      "Medium",
      "High",
      "High",
      "Very high",
      "Very high",
    ]);
  });

  it("reads the next ball's pressure, across the innings break", () => {
    expect(pressureAt(timeline, -1)).toEqual({ pressure: 40, leverage: 0.7, inningsNo: 1 });
    expect(pressureAt(timeline, 0)).toEqual({ pressure: 30, leverage: 0.6, inningsNo: 1 });
    expect(pressureAt(timeline, 1)).toEqual({ pressure: 55, leverage: 0.9, inningsNo: 2 });
    expect(pressureAt(timeline, 5)).toBeNull();
  });

  it("reads momentum for the batting side", () => {
    expect(momentumAt(timeline, -1)).toBeNull();
    expect(momentumAt(timeline, 1)).toEqual({ points: -3.4, inningsNo: 1 });
  });

  it("builds the series and the peaks, one per over", () => {
    const series = pressureSeries(timeline, 4);
    expect(series.map((p) => p.index)).toEqual([-1, 0, 2, 3, 4]);
    expect(pressurePeaks(timeline, 5).map((p) => p.index)).toEqual([3, 4, 0]);
  });

  it("formats leverage", () => {
    expect(formatLeverage(0.84)).toBe("0.8×");
    expect(formatLeverage(12.4)).toBe("12×");
  });
});
