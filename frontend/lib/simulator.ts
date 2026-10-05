/**
 * Match simulator and what-if helpers. The simulations themselves run in the
 * API (criciq_core.simulation); this module shapes requests and labels results.
 */
import type { SimPlayer, SimulationRequest, Timeline } from "@/lib/api/types";

/** The engine needs this many bowling options: 20 overs at four each. */
export const MIN_BOWLERS = 5;
export const XI_SIZE = 11;
export const DEFAULT_SIMULATIONS = 10_000;
export const WHATIF_SIMULATIONS = 4_000;

/** Series colours for the two sides, as on Compare. */
export const SIM_SERIES = {
  a: { color: "var(--chart-1)" },
  b: { color: "var(--chart-2)" },
} as const;

export type BatFirst = "a" | "b" | "toss";

export interface XIState {
  team: string | null;
  players: SimPlayer[];
  bowlers: string[];
}

/** Why a side cannot be simulated yet, or null when it is ready. */
export function sideIssue(xi: XIState): string | null {
  if (xi.players.length !== XI_SIZE) {
    return `Pick ${XI_SIZE} players (${xi.players.length} so far).`;
  }
  const bowlers = xi.bowlers.filter((id) => xi.players.some((p) => p.player_id === id));
  if (bowlers.length < MIN_BOWLERS) {
    return `Pick at least ${MIN_BOWLERS} bowling options (${bowlers.length} so far).`;
  }
  return null;
}

export function simulationRequest(a: XIState, b: XIState, batFirst: BatFirst): SimulationRequest {
  const side = (xi: XIState) => ({
    franchise_id: xi.team,
    batters: xi.players.map((p) => p.player_id),
    bowlers: xi.bowlers.filter((id) => xi.players.some((p) => p.player_id === id)),
  });
  return {
    a: side(a),
    b: side(b),
    bat_first: batFirst === "toss" ? null : batFirst,
    simulations: DEFAULT_SIMULATIONS,
  };
}

/** A copy of ``items`` with the item at ``from`` moved to ``to``. */
export function move<T>(items: readonly T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length || from === to) return [...items];
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export function pct(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}%`;
}

/** Legal balls as scoreboard overs: 57 -> "9.3". */
export function oversText(balls: number): string {
  return `${Math.floor(balls / 6)}.${balls % 6}`;
}

export interface WhatIfPosition {
  inningsNo: 1 | 2;
  seqNo: number;
}

/**
 * The replay position a what-if starts from: after the ball at ``cursor``
 * (before the first ball when the cursor is -1). Between innings it is the start
 * of the chase. There is nothing to simulate once the match is over or in a
 * super over.
 */
export function whatIfPosition(timeline: Timeline, cursor: number): WhatIfPosition | null {
  const superOver = new Set(
    timeline.innings.filter((i) => i.is_super_over).map((i) => i.innings_no),
  );
  if (cursor < 0) return timeline.deliveries.length ? { inningsNo: 1, seqNo: 0 } : null;
  const ball = timeline.deliveries[cursor];
  const next = timeline.deliveries[cursor + 1];
  if (!ball || !next || superOver.has(ball.innings_no) || superOver.has(next.innings_no)) {
    return null;
  }
  if (next.innings_no !== ball.innings_no) {
    return next.innings_no === 2 ? { inningsNo: 2, seqNo: 0 } : null;
  }
  if (ball.innings_no !== 1 && ball.innings_no !== 2) return null;
  return { inningsNo: ball.innings_no, seqNo: ball.seq_no };
}

/** "+18.2 pts", "−4.0 pts" with a true minus sign. */
export function pointsText(delta: number): string {
  const text = Math.abs(delta).toFixed(1);
  if (Number(text) === 0) return "no change";
  return `${delta > 0 ? "+" : "−"}${text} pts`;
}
