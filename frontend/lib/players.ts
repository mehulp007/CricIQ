/**
 * Player Lab presentation helpers. Numbers arrive from the API already
 * computed (including "par": what an average IPL player would have produced
 * from the same balls); this module only formats and labels them.
 */
import type { Percentile, PlayerRole } from "@/lib/api/types";

/** Chart roles: the player in the brand colour, par in neutral grey. */
export const PLAYER_SERIES = {
  player: { color: "var(--chart-3)", label: "Player" },
  par: { color: "var(--chart-5)", label: "Par" },
} as const;

/** Splits on fewer balls than this are flagged as a small sample. */
export const SMALL_SAMPLE_BALLS = 60;

export function roleLabel(role: PlayerRole, isKeeper: boolean): string {
  if (isKeeper) return role === "batter" ? "Wicketkeeper-batter" : "Wicketkeeper";
  return { batter: "Batter", bowler: "Bowler", all_rounder: "All-rounder" }[role];
}

export function handLabel(hand: "right" | "left" | null | undefined): string | null {
  if (!hand) return null;
  return hand === "right" ? "Right-hand bat" : "Left-hand bat";
}

const MINUS = "−";

/** "+3.4", "−0.5", "0.0" with a true minus sign. */
export function signed(value: number, digits = 1): string {
  const text = Math.abs(value).toFixed(digits);
  if (Number(text) === 0) return (0).toFixed(digits);
  return `${value > 0 ? "+" : MINUS}${text}`;
}

/** 1 -> "1st", 22 -> "22nd", 13 -> "13th". */
export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${{ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th"}`;
}

/** A rate, or a dash when there is nothing to divide by. */
export function rate(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

/** Bowling figures in the usual wickets/runs form, e.g. "5/21". */
export function figures(wickets: number, runs: number): string {
  return `${wickets}/${runs}`;
}

/** [2008, 2009, 2010, 2014] -> "2008–2010, 2014". */
export function seasonRanges(seasons: number[]): string {
  const sorted = [...new Set(seasons)].sort((a, b) => a - b);
  const ranges: string[] = [];
  let start = sorted[0];
  let prev = sorted[0];
  for (const year of [...sorted.slice(1), Number.NaN]) {
    if (year === prev + 1) {
      prev = year;
      continue;
    }
    ranges.push(start === prev ? String(start) : `${start}–${prev}`);
    start = year;
    prev = year;
  }
  return sorted.length ? ranges.join(", ") : "";
}

/** A percentile metric's value with its unit, e.g. "+3.4 per 100 balls". */
export function formatMetric(item: Pick<Percentile, "value" | "unit">): string {
  if (item.value === null || item.value === undefined) return "—";
  switch (item.unit) {
    case "runs_per_100":
      return `${signed(item.value)} per 100 balls`;
    case "runs_per_over":
      return `${signed(item.value, 2)} per over`;
    case "percent":
      return `${signed(item.value, 0)}%`;
    case "points":
      return `${signed(item.value)} pts`;
  }
}

/** Whether a difference from par is good for the player. */
export function isBetter(delta: number, higherIsBetter: boolean): boolean {
  return higherIsBetter ? delta > 0 : delta < 0;
}

/** Win probability added, in wins (a sum of probability changes). */
export function formatWpa(wpa: number | null | undefined): string {
  return wpa === null || wpa === undefined ? "—" : signed(wpa, 2);
}

export const ROLE_FILTERS = [
  { value: "batter", label: "Batters" },
  { value: "bowler", label: "Bowlers" },
  { value: "all_rounder", label: "All-rounders" },
  { value: "keeper", label: "Wicketkeepers" },
] as const;

export const PLAYER_SORTS = [
  { value: "matches", label: "Most matches" },
  { value: "runs", label: "Most runs" },
  { value: "wickets", label: "Most wickets" },
  { value: "recent", label: "Most recent" },
  { value: "name", label: "Name" },
] as const;

const DISMISSALS: Record<string, string> = {
  caught: "Caught",
  bowled: "Bowled",
  lbw: "LBW",
  "run out": "Run out",
  stumped: "Stumped",
  "caught and bowled": "Caught and bowled",
  "hit wicket": "Hit wicket",
  "retired out": "Retired out",
  "obstructing the field": "Obstructing the field",
};

export function dismissalLabel(kind: string): string {
  return DISMISSALS[kind] ?? kind.charAt(0).toUpperCase() + kind.slice(1);
}

/** Parse a season from a search param; anything else is ignored. */
export function parseSeason(value: string | string[] | undefined): number | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  const year = Number(raw);
  return Number.isInteger(year) && year >= 2008 && year <= 2100 ? year : undefined;
}
