/**
 * First-innings score projection in the replay. The API stores quantiles of the
 * final total after every first-innings ball; everything here derives from them.
 * The CDF construction mirrors `criciq_ml.projection.cdf_points`.
 */
import type { Timeline } from "@/lib/api/types";

export interface Projection {
  quantiles: number[];
  levels: number[];
  current: number;
  median: number;
  low: number; // 10%
  high: number; // 90%
}

/** The projection after the cursor ball (before the first ball at -1); null outside a first innings. */
export function projectionAt(timeline: Timeline, cursor: number): Projection | null {
  const levels = timeline.score_projection?.levels;
  if (!levels) return null;
  const d = cursor >= 0 ? timeline.deliveries[cursor] : null;
  const quantiles = d ? d.projection : timeline.innings[0]?.projection_start;
  if (!quantiles || (d && d.innings_no !== 1)) return null;
  const at = (level: number) => quantiles[levels.indexOf(level)];
  return {
    quantiles,
    levels,
    current: d?.team_runs ?? 0,
    median: at(0.5),
    low: at(0.1),
    high: at(0.9),
  };
}

/** Points of the piecewise-linear CDF: from the current score to just past the 95% quantile. */
export function cdfPoints(p: Projection): { x: number[]; p: number[] } {
  const q = p.quantiles;
  const top = q[q.length - 1] + 2 * (q[q.length - 1] - q[q.length - 2]) + 1;
  const x = [Math.min(p.current, q[0]), ...q, top];
  for (let i = 1; i < x.length; i++) x[i] = Math.max(x[i], x[i - 1]);
  return { x, p: [0, ...p.levels, 1] };
}

/** P(final total >= threshold). */
export function probabilityAtLeast(p: Projection, threshold: number): number {
  if (threshold <= p.current) return 1;
  const { x, p: probs } = cdfPoints(p);
  if (threshold >= x[x.length - 1]) return 0;
  for (let i = 1; i < x.length; i++) {
    if (threshold <= x[i]) {
      const span = x[i] - x[i - 1];
      const t = span > 0 ? (threshold - x[i - 1]) / span : 1;
      return 1 - (probs[i - 1] + t * (probs[i] - probs[i - 1]));
    }
  }
  return 0;
}

/** Four round totals around the projection, so the odds are informative at any stage. */
export function thresholdsFor(p: Projection): number[] {
  const base = Math.round(p.median / 10) * 10;
  return [base - 20, base - 10, base + 10, base + 20].filter((t) => t > p.current);
}

export interface ConePoint {
  x: number; // overs
  band: [number, number];
  median: number;
}

/** A fan from the current score to the projected range at the end of the innings. */
export function projectionCone(timeline: Timeline, cursor: number): ConePoint[] {
  const p = projectionAt(timeline, cursor);
  if (!p) return [];
  const d = cursor >= 0 ? timeline.deliveries[cursor] : null;
  const maxBalls = timeline.innings[0]?.max_balls ?? 120;
  const start = (d?.legal_ball_no ?? 0) / 6;
  return [
    { x: start, band: [p.current, p.current], median: p.current },
    { x: maxBalls / 6, band: [p.low, p.high], median: p.median },
  ];
}
