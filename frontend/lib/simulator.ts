/**
 * Match simulator and what-if helpers. The simulations themselves run in the
 * API (criciq_core.simulation); this module shapes requests and labels results.
 */
import type {
  SimSeason,
  SimSquad,
  SimulationRequest,
  SquadPlayer,
  Timeline,
} from "@/lib/api/types";

/** The engine needs this many bowling options: 20 overs at four each, or 50 at ten. */
export const MIN_BOWLERS = 5;
export const XI_SIZE = 11;
/** A player added to the XI bowls by default with a quota of recent overs (four in a T20). */
export const REGULAR_BOWLER_OVERS = 4;
export const DEFAULT_SIMULATIONS = 10_000;
export const WHATIF_SIMULATIONS = 4_000;

/** Series colours for the two sides, as on Compare. */
export const SIM_SERIES = {
  a: { color: "var(--chart-1)" },
  b: { color: "var(--chart-2)" },
} as const;

export type BatFirst = "a" | "b" | "toss";

/** One side: its squad that season, the XI picked from it and its bowling options. */
export interface XIState {
  team: string | null;
  squad: SquadPlayer[];
  players: SquadPlayer[];
  bowlers: string[];
}

export const EMPTY_XI: XIState = { team: null, squad: [], players: [], bowlers: [] };

type Param = string | string[] | undefined;

function single(value: Param): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** The season asked for in the URL, or the latest one. */
export function pickSeason(seasons: SimSeason[], raw: Param): SimSeason | null {
  const year = Number(single(raw));
  return seasons.find((s) => s.season === year) ?? seasons[0] ?? null;
}

const PREFERRED = ["MI", "CSK"];

/**
 * Two different sides from a season: the ones asked for when they played that
 * season, otherwise MI and CSK, otherwise its first sides.
 */
export function defaultTeams(
  season: SimSeason,
  rawA?: Param,
  rawB?: Param,
): [string | null, string | null] {
  const ids = season.teams.map((t) => t.team.franchise_id);
  const chosen: string[] = [];
  for (const want of [single(rawA)?.toUpperCase(), single(rawB)?.toUpperCase()]) {
    const fallback = [...PREFERRED, ...ids].find((id) => ids.includes(id) && !chosen.includes(id));
    const id = want && ids.includes(want) && !chosen.includes(want) ? want : fallback;
    if (id) chosen.push(id);
  }
  return [chosen[0] ?? null, chosen[1] ?? null];
}

/** A side as the season left it: its last XI that season, in batting order. */
export function fromSquad(squad: SimSquad | null): XIState {
  if (!squad) return EMPTY_XI;
  const byId = new Map(squad.players.map((p) => [p.player_id, p]));
  const players = squad.xi.flatMap((id) => byId.get(id) ?? []);
  return { team: squad.team.franchise_id, squad: squad.players, players, bowlers: squad.bowlers };
}

/** Squad players not in the XI, most appearances first. */
export function bench(xi: XIState): SquadPlayer[] {
  const picked = new Set(xi.players.map((p) => p.player_id));
  return xi.squad.filter((p) => !picked.has(p.player_id));
}

/** Add a squad player at the end of the batting order; regular bowlers (a quota of recent
 * overs: four in a T20, ten in an ODI) bowl. */
export function addPlayer(
  xi: XIState,
  playerId: string,
  regularOvers: number = REGULAR_BOWLER_OVERS,
): XIState {
  const player = xi.squad.find((p) => p.player_id === playerId);
  if (!player || xi.players.length >= XI_SIZE || xi.players.includes(player)) return xi;
  return {
    ...xi,
    players: [...xi.players, player],
    bowlers: player.recent_overs >= regularOvers ? [...xi.bowlers, playerId] : xi.bowlers,
  };
}

/** Move a player from the XI back to the bench. */
export function removePlayer(xi: XIState, playerId: string): XIState {
  return {
    ...xi,
    players: xi.players.filter((p) => p.player_id !== playerId),
    bowlers: xi.bowlers.filter((id) => id !== playerId),
  };
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

export function simulationRequest(
  a: XIState,
  b: XIState,
  batFirst: BatFirst,
  season: number | null,
): SimulationRequest {
  const side = (xi: XIState) => ({
    franchise_id: xi.team,
    batters: xi.players.map((p) => p.player_id),
    bowlers: xi.bowlers.filter((id) => xi.players.some((p) => p.player_id === id)),
  });
  return {
    a: side(a),
    b: side(b),
    bat_first: batFirst === "toss" ? null : batFirst,
    season,
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

/** Bowling overs as on a scorecard: 24 -> "4", 21 -> "3.3". */
export function bowlingOvers(balls: number | null | undefined): string {
  if (balls === null || balls === undefined) return "—";
  return balls % 6 === 0 ? String(balls / 6) : oversText(balls);
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
