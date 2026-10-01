/**
 * Matchup Lab presentation helpers. The API returns three readings of every
 * batter-bowler record: what happened (raw), what each player's overall
 * record predicts for those balls (expected), and the head-to-head record
 * shrunk towards that expectation (estimate).
 */
import type { Interval, MatchupDetail, MatchupPhase } from "@/lib/api/types";

export const READINGS = {
  raw: { label: "Head-to-head", color: "var(--chart-2)" },
  estimate: { label: "CricIQ estimate", color: "var(--chart-3)" },
  expected: { label: "Expected from overall form", color: "var(--chart-5)" },
} as const;

export type Reading = keyof typeof READINGS;

export const SAMPLE_LABELS: Record<MatchupDetail["sample"]["level"], string> = {
  none: "Never met",
  tiny: "Tiny sample",
  small: "Small sample",
  moderate: "Moderate sample",
  large: "Large sample",
};

export const PHASE_OPTIONS: { value: MatchupPhase; label: string }[] = [
  { value: "powerplay", label: "Powerplay" },
  { value: "middle", label: "Middle overs" },
  { value: "death", label: "Death overs" },
];

export function parsePhase(value: string | string[] | undefined): MatchupPhase | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return PHASE_OPTIONS.find((p) => p.value === raw)?.value;
}

/** Player ids are Cricsheet registry ids: short hex strings. */
export function parsePlayerId(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw && /^[\w-]{1,32}$/.test(raw) ? raw : undefined;
}

export interface MetricSpec {
  key: "strike_rate" | "balls_per_dismissal" | "dot_pct" | "boundary_pct";
  label: string;
  /** Which direction favours the batter. */
  batterWantsHigh: boolean;
  digits: number;
  suffix?: string;
}

export const METRICS: MetricSpec[] = [
  { key: "strike_rate", label: "Strike rate", batterWantsHigh: true, digits: 1 },
  { key: "balls_per_dismissal", label: "Balls per dismissal", batterWantsHigh: true, digits: 0 },
  { key: "dot_pct", label: "Dot balls", batterWantsHigh: false, digits: 1, suffix: "%" },
  { key: "boundary_pct", label: "Boundaries", batterWantsHigh: true, digits: 1, suffix: "%" },
];

export function formatValue(value: number | null | undefined, spec: MetricSpec): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(spec.digits)}${spec.suffix ?? ""}`;
}

/** Shared axis for one metric's intervals, padded and clipped to sensible bounds. */
export function axisFor(intervals: (Interval | null | undefined)[]): [number, number] {
  const values = intervals.flatMap((i) =>
    i ? [i.value, i.low, i.high].filter((v): v is number => v !== null && v !== undefined) : [],
  );
  if (!values.length) return [0, 1];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = Math.max((hi - lo) * 0.08, 1);
  return [Math.max(0, lo - pad), hi + pad];
}

/** Position (0-100%) of a value on an axis, clamped. */
export function position(value: number, [lo, hi]: [number, number]): number {
  if (hi <= lo) return 50;
  return Math.min(100, Math.max(0, ((value - lo) / (hi - lo)) * 100));
}

export function percent(p: number, digits = 1): string {
  return `${(p * 100).toFixed(digits)}%`;
}

/** How much the estimate leans on head-to-head history, in plain words. */
export function weightSentence(weight: number, kappa: number): string {
  const share = Math.round(weight * 100);
  return `Head-to-head balls carry ${share}% of the estimate; the rest comes from each player's overall record (the prior is worth ${Math.round(kappa)} balls).`;
}
