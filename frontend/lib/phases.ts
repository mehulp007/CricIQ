/**
 * Phase Analysis helpers: the page's URL filters, checked before they reach the API, and
 * the choices and colours its pieces share.
 */

import type { MatchFormat } from "@/lib/competitions";

type Raw = Record<string, string | string[] | undefined>;

function one(raw: Raw, key: string): string | undefined {
  const value = raw[key];
  return Array.isArray(value) ? value[0] : value;
}

function int(value: string | undefined, min: number, max: number): number | undefined {
  if (value === undefined || !/^\d+$/.test(value)) return undefined;
  const n = Number(value);
  return n >= min && n <= max ? n : undefined;
}

/** The innings a format can be filtered to (two in limited overs, four in a Test). */
export function maxInnings(format: MatchFormat): number {
  return format === "Test" ? 4 : 2;
}

/**
 * The API query for the page's search params: seasons (``from``, ``to``), ``team``,
 * ``venue``, ``innings`` and ``min_balls``. Anything malformed is dropped, so a bad link
 * shows the unfiltered page rather than an error.
 */
export function phaseQuery(raw: Raw, format: MatchFormat): URLSearchParams {
  const query = new URLSearchParams();
  const from = int(one(raw, "from"), 2000, 2100);
  const to = int(one(raw, "to"), 2000, 2100);
  if (from !== undefined && (to === undefined || from <= to)) query.set("from", String(from));
  if (to !== undefined && (from === undefined || from <= to)) query.set("to", String(to));
  const team = one(raw, "team");
  if (team && /^[A-Za-z0-9]{2,8}$/.test(team)) query.set("team", team);
  const venue = one(raw, "venue");
  if (venue && venue.length <= 80) query.set("venue", venue);
  const innings = int(one(raw, "innings"), 1, maxInnings(format));
  if (innings !== undefined) query.set("innings", String(innings));
  const minBalls = int(one(raw, "min_balls"), 1, 10_000);
  if (minBalls !== undefined) query.set("min_balls", String(minBalls));
  return query;
}

/** The innings filter's choices: "Batting first" and "Chasing", or a Test's four innings. */
export function inningsChoices(format: MatchFormat): { value: string; label: string }[] {
  if (format === "Test") {
    return ["1st", "2nd", "3rd", "4th"].map((label, i) => ({
      value: String(i + 1),
      label: `${label} innings`,
    }));
  }
  return [
    { value: "1", label: "Batting first" },
    { value: "2", label: "Chasing" },
  ];
}

/** Minimum balls in a phase for its leaders. */
export const MIN_BALL_CHOICES = [1, 30, 60, 120, 300, 600, 1000] as const;

/** A phase's colour, by its place in the innings (the chart tokens follow the theme). */
export function phaseColor(index: number): string {
  return `var(--chart-${(index % 5) + 1})`;
}

/** "Overs 1–6", "Overs 81 onwards". */
export function oversLabel(first: number, last: number | null): string {
  return last === null ? `Overs ${first} onwards` : `Overs ${first}–${last}`;
}

/** A rate or average for a table cell ("—" without one). */
export function fig(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}
