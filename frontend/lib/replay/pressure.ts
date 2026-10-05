/**
 * Pressure and momentum in the replay, read from the timeline.
 *
 * After every ball the API stores the pressure on the *next* ball (a 0-100
 * percentile of leverage: how much that ball can move the win probability,
 * compared with every IPL ball) and the batting side's momentum (its change in
 * win probability over the last 12 legal balls, in points).
 */
import type { Timeline } from "@/lib/api/types";
import { matchOvers } from "@/lib/replay/win-probability";

export const PRESSURE_BANDS = [
  { label: "Low", from: 0 },
  { label: "Medium", from: 50 },
  { label: "High", from: 80 },
  { label: "Very high", from: 95 },
] as const;

export type PressureBand = (typeof PRESSURE_BANDS)[number]["label"];

export function pressureBand(pressure: number): PressureBand {
  let band: PressureBand = "Low";
  for (const b of PRESSURE_BANDS) if (pressure >= b.from) band = b.label;
  return band;
}

export interface PressureReading {
  pressure: number;
  leverage: number;
  /** The innings the next ball belongs to. */
  inningsNo: number;
}

/** Pressure on the ball after the cursor (before the first ball at -1); null once an innings is over. */
export function pressureAt(timeline: Timeline, cursor: number): PressureReading | null {
  if (cursor < 0) {
    const first = timeline.innings[0];
    if (first?.pressure_start === null || first?.pressure_start === undefined) return null;
    return { pressure: first.pressure_start, leverage: first.leverage_start ?? 1, inningsNo: 1 };
  }
  const d = timeline.deliveries[cursor];
  if (!d) return null;
  if (d.pressure !== null && d.pressure !== undefined) {
    return { pressure: d.pressure, leverage: d.leverage ?? 1, inningsNo: d.innings_no };
  }
  // End of the first innings: the next ball is the chase's first.
  const next = timeline.deliveries[cursor + 1];
  const start = next && timeline.innings.find((i) => i.innings_no === next.innings_no);
  if (next && next.innings_no !== d.innings_no && start?.pressure_start != null) {
    return {
      pressure: start.pressure_start,
      leverage: start.leverage_start ?? 1,
      inningsNo: next.innings_no,
    };
  }
  return null;
}

export interface MomentumReading {
  /** Points of win probability gained by the batting side over the last 12 legal balls. */
  points: number;
  inningsNo: number;
}

export function momentumAt(timeline: Timeline, cursor: number): MomentumReading | null {
  const d = cursor >= 0 ? timeline.deliveries[cursor] : undefined;
  if (!d || d.momentum === null || d.momentum === undefined) return null;
  return { points: d.momentum, inningsNo: d.innings_no };
}

export interface PressurePoint {
  x: number; // match overs (the chase starts at 20)
  pressure: number;
  leverage: number;
  index: number;
  label: string;
}

/** Pressure after every ball up to the cursor, on the match-overs axis. */
export function pressureSeries(timeline: Timeline, cursor: number): PressurePoint[] {
  const points: PressurePoint[] = [];
  const first = timeline.innings[0];
  if (first?.pressure_start !== null && first?.pressure_start !== undefined) {
    points.push({
      x: 0,
      pressure: first.pressure_start,
      leverage: first.leverage_start ?? 1,
      index: -1,
      label: "Start",
    });
  }
  timeline.deliveries.forEach((d, index) => {
    if (index > cursor || d.pressure === null || d.pressure === undefined) return;
    points.push({
      x: matchOvers(d),
      pressure: d.pressure,
      leverage: d.leverage ?? 1,
      index,
      label: d.ball_label ?? "",
    });
  });
  return points;
}

/** The highest-pressure moments so far (one per over at most), highest first. */
export function pressurePeaks(timeline: Timeline, cursor: number, count = 3): PressurePoint[] {
  const best = new Map<string, PressurePoint>();
  for (const p of pressureSeries(timeline, cursor)) {
    if (p.index < 0) continue;
    const d = timeline.deliveries[p.index];
    const key = `${d.innings_no}-${d.over_no}`;
    const current = best.get(key);
    if (!current || p.leverage > current.leverage) best.set(key, p);
  }
  return [...best.values()].sort((a, b) => b.leverage - a.leverage).slice(0, count);
}

/** "2.4×" for a leverage, never shown with spurious precision. */
export function formatLeverage(leverage: number): string {
  return `${leverage >= 10 ? Math.round(leverage) : leverage.toFixed(1)}×`;
}
