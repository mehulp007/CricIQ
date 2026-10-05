import "server-only";

import type {
  MatchPage,
  MatchupDetail,
  MatchupList,
  MatchupPhase,
  Meta,
  PlayerPage,
  PlayerProfile,
  PlayerSplits,
  SimilarPlayers,
  SimulationRequest,
  SimulationResult,
  SimXI,
  Standings,
  StateRequest,
  StateResult,
  HeadToHead,
  TeamProfile,
  TeamsOverview,
  Timeline,
} from "./types";

/**
 * Server-side client for the CricIQ API. Historical data only changes when the
 * API is redeployed, so responses are cached by Next.js for a day.
 */
const API_URL = process.env.CRICIQ_API_URL ?? "http://localhost:8000";

// The free-tier API sleeps when idle and can take ~30-50s to wake.
const TIMEOUT_MS = 55_000;
const REVALIDATE_SECONDS = 86_400;
// Every API response carries this cache tag, so an API redeploy can be followed
// by one invalidation instead of waiting a day (see docs/deployment.md).
export const API_CACHE_TAG = "criciq-api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiGet<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      next: { revalidate: REVALIDATE_SECONDS, tags: [API_CACHE_TAG] },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (cause) {
    throw new ApiError(`CricIQ API unreachable (${String(cause)})`, null);
  }
  if (!response.ok) {
    throw new ApiError(`CricIQ API returned ${response.status} for ${path}`, response.status);
  }
  return (await response.json()) as T;
}

export interface MatchQuery {
  season?: number;
  team?: string;
  playoffs?: boolean;
  sort?: "latest" | "oldest";
  page?: number;
  pageSize?: number;
}

export function getMatches(query: MatchQuery = {}): Promise<MatchPage> {
  const params = new URLSearchParams();
  if (query.season) params.set("season", String(query.season));
  if (query.team) params.set("team", query.team);
  if (query.playoffs !== undefined) params.set("playoffs", String(query.playoffs));
  if (query.sort) params.set("sort", query.sort);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 24));
  return apiGet<MatchPage>(`/api/v1/matches?${params}`);
}

export function getMeta(): Promise<Meta> {
  return apiGet<Meta>("/api/v1/meta");
}

export function getTimeline(matchId: number): Promise<Timeline> {
  return apiGet<Timeline>(`/api/v1/matches/${matchId}/timeline`);
}

export type PlayerRoleFilter = "batter" | "bowler" | "all_rounder" | "keeper";
export type PlayerSort = "matches" | "runs" | "wickets" | "recent" | "name";

export interface PlayerQuery {
  q?: string;
  role?: PlayerRoleFilter;
  season?: number;
  team?: string;
  sort?: PlayerSort;
  page?: number;
  pageSize?: number;
}

export function getPlayers(query: PlayerQuery = {}): Promise<PlayerPage> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.role) params.set("role", query.role);
  if (query.season) params.set("season", String(query.season));
  if (query.team) params.set("team", query.team);
  if (query.sort) params.set("sort", query.sort);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 30));
  return apiGet<PlayerPage>(`/api/v1/players?${params}`);
}

/** Seasons to include, inclusive; omitted ends mean the whole career. */
export interface SeasonWindow {
  from?: number;
  to?: number;
}

function windowQuery(window: SeasonWindow): string {
  const params = new URLSearchParams();
  if (window.from) params.set("from", String(window.from));
  if (window.to) params.set("to", String(window.to));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getPlayer(playerId: string, window: SeasonWindow = {}): Promise<PlayerProfile> {
  return apiGet<PlayerProfile>(
    `/api/v1/players/${encodeURIComponent(playerId)}${windowQuery(window)}`,
  );
}

export function getPlayerSplits(
  playerId: string,
  window: SeasonWindow = {},
): Promise<PlayerSplits> {
  return apiGet<PlayerSplits>(
    `/api/v1/players/${encodeURIComponent(playerId)}/splits${windowQuery(window)}`,
  );
}

export function getSimilarPlayers(
  playerId: string,
  window: SeasonWindow = {},
): Promise<SimilarPlayers> {
  return apiGet<SimilarPlayers>(
    `/api/v1/players/${encodeURIComponent(playerId)}/similar${windowQuery(window)}`,
  );
}

export type MatchupSort = "balls" | "batter_edge" | "bowler_edge";

export interface MatchupQuery extends SeasonWindow {
  batter?: string;
  bowler?: string;
  minBalls?: number;
  sort?: MatchupSort;
  page?: number;
  pageSize?: number;
}

export function getMatchups(query: MatchupQuery = {}): Promise<MatchupList> {
  const params = new URLSearchParams();
  if (query.batter) params.set("batter", query.batter);
  if (query.bowler) params.set("bowler", query.bowler);
  if (query.from) params.set("from", String(query.from));
  if (query.to) params.set("to", String(query.to));
  if (query.minBalls) params.set("min_balls", String(query.minBalls));
  if (query.sort) params.set("sort", query.sort);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 25));
  return apiGet<MatchupList>(`/api/v1/matchups?${params}`);
}

export function getMatchup(
  batterId: string,
  bowlerId: string,
  options: SeasonWindow & { phase?: MatchupPhase } = {},
): Promise<MatchupDetail> {
  const params = new URLSearchParams();
  if (options.from) params.set("from", String(options.from));
  if (options.to) params.set("to", String(options.to));
  if (options.phase) params.set("phase", options.phase);
  const query = params.toString();
  return apiGet<MatchupDetail>(
    `/api/v1/matchups/${encodeURIComponent(batterId)}/${encodeURIComponent(bowlerId)}${query ? `?${query}` : ""}`,
  );
}

export function getTeams(): Promise<TeamsOverview> {
  return apiGet<TeamsOverview>("/api/v1/teams");
}

export function getStandings(season: number): Promise<Standings> {
  return apiGet<Standings>(`/api/v1/teams/standings/${season}`);
}

export function getTeam(franchiseId: string, window: SeasonWindow = {}): Promise<TeamProfile> {
  return apiGet<TeamProfile>(
    `/api/v1/teams/${encodeURIComponent(franchiseId)}${windowQuery(window)}`,
  );
}

export function getHeadToHead(
  a: string,
  b: string,
  window: SeasonWindow = {},
): Promise<HeadToHead> {
  const params = new URLSearchParams({ a, b });
  if (window.from) params.set("from", String(window.from));
  if (window.to) params.set("to", String(window.to));
  return apiGet<HeadToHead>(`/api/v1/teams/h2h?${params}`);
}

/** POST without caching: simulations depend on the request body. */
async function apiPost<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (cause) {
    throw new ApiError(`CricIQ API unreachable (${String(cause)})`, null);
  }
  if (!response.ok) {
    let detail = "";
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? "";
    } catch {
      // not JSON
    }
    throw new ApiError(
      detail || `CricIQ API returned ${response.status} for ${path}`,
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function getLatestXI(franchiseId: string): Promise<SimXI> {
  return apiGet<SimXI>(`/api/v1/simulate/xi/${encodeURIComponent(franchiseId)}`);
}

export function orderXI(playerIds: string[]): Promise<SimXI> {
  return apiPost<SimXI>("/api/v1/simulate/xi", { player_ids: playerIds });
}

export function simulateMatch(request: SimulationRequest): Promise<SimulationResult> {
  return apiPost<SimulationResult>("/api/v1/simulate/match", request);
}

export function simulateState(request: StateRequest): Promise<StateResult> {
  return apiPost<StateResult>("/api/v1/simulate/state", request);
}
