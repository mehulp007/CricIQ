/**
 * Team Analytics presentation helpers. Records, league tables and expectations
 * arrive computed from the API; this module only labels and formats them.
 */
import type { Finish, H2HExpectation, TeamRecord } from "@/lib/api/types";
import { seasonLabel, type CompetitionId } from "@/lib/competitions";
import { ordinal, signed } from "@/lib/players";

/** Franchise ids are short upper-case codes, e.g. "MI" or "PBKS". */
export function parseTeamId(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  const id = raw?.trim().toUpperCase();
  return id && /^[A-Z]{2,5}$/.test(id) ? id : undefined;
}

const EXITS: Record<string, string> = {
  "Qualifier 1": "Out in Qualifier 1",
  "Qualifier 2": "Out in Qualifier 2",
  Eliminator: "Out in the Eliminator",
  "Elimination Final": "Out in the Elimination Final",
  "Semi Final": "Out in the semi-finals",
  // 2010: the beaten semi-finalists played off for third place.
  "3rd Place Play-Off": "Semi-finalists",
};

/** How a season ended: "Champions", "Out in Qualifier 2", "6th of 10". */
export function finishLabel(
  finish: Finish,
  exitStage: string | null | undefined,
  position: number,
  teams: number,
): string {
  if (finish === "champion") return "Champions";
  if (finish === "runner_up") return "Runners-up";
  if (finish === "playoffs") return (exitStage && EXITS[exitStage]) ?? "Playoffs";
  return `${ordinal(position)} of ${teams}`;
}

/** Ordering for finishes, best first. */
export const FINISH_RANK: Record<Finish, number> = {
  champion: 0,
  runner_up: 1,
  playoffs: 2,
  league: 3,
};

/** "148–117" plus "· 1 NR" when there were no results. */
export function recordText(record: Pick<TeamRecord, "won" | "lost" | "no_result">): string {
  const base = `${record.won}–${record.lost}`;
  return record.no_result ? `${base} · ${record.no_result} NR` : base;
}

export function pct(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}%`;
}

/** Net run rate with its sign, e.g. "+0.421" or "−0.011". */
export function formatNrr(nrr: number | null | undefined): string {
  return nrr === null || nrr === undefined ? "—" : signed(nrr, 3);
}

export function h2hHref(a: string, b: string, window: { from?: number; to?: number } = {}) {
  const params = new URLSearchParams({ a, b });
  if (window.from) params.set("from", String(window.from));
  if (window.to) params.set("to", String(window.to));
  return `/teams/h2h?${params}`;
}

/**
 * Reading of a head-to-head record against the form expectation: is A's tally
 * outside the range chance alone produces nine times in ten? With dozens of
 * rivalries, a few land outside it by chance, so even then it is no forecast.
 */
export function expectationVerdict(e: H2HExpectation, a: string, b: string): string {
  const diff = e.a_won - e.a_expected;
  const size = Math.abs(diff) < 0.5 ? "" : ` by ${Math.abs(diff).toFixed(1)} wins`;
  const outside =
    "outside the range chance gives nine times in ten. With dozens of rivalries, a few land there by chance alone, and past records do not predict the next meeting.";
  if (e.a_won > e.high) return `${a} have beaten form${size}, ${outside}`;
  if (e.a_won < e.low) return `${b} have beaten form${size}, ${outside}`;
  return `Within the range chance alone produces${size ? ` (${signed(diff, 1)} wins)` : ""}: no sign of a hold either way.`;
}

/** "2008–2026", or one year; "2011/12–2025/26" for a competition named that way. */
export function seasonSpan(first: number, last: number, competition?: CompetitionId): string {
  const label = (year: number) => (competition ? seasonLabel(competition, year) : String(year));
  return first === last ? label(first) : `${label(first)}–${label(last)}`;
}
