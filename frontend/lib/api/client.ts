import "server-only";

import type { CompetitionId } from "@/lib/competitions";

import type {
  CompetitionList,
  MatchPage,
  MatchupDetail,
  MatchupList,
  MatchupPhase,
  Meta,
  PlayerCareers,
  PlayerPage,
  PlayerProfile,
  PlayerSplits,
  SimilarPlayers,
  SimSeason,
  SimSquad,
  SimulationRequest,
  SimulationResult,
  Standings,
  StateRequest,
  StateResult,
  HeadToHead,
  TeamProfile,
  TeamsOverview,
  Timeline,
} from "./types";
import { withVersion } from "./version";

/**
 * Server-side client for the CricIQ API (`/api/v2`). Every page of a
 * competition reads that competition's data (`/api/v2/{competition}/...`).
 * Responses are cached by Next.js for a day, keyed by the data version (see
 * ./version): the metadata that carries it is refreshed every few minutes, so
 * new data from a sync shows up quickly.
 */
const API_URL = process.env.CRICIQ_API_URL ?? "http://localhost:8000";

// The free-tier API sleeps when idle and can take ~30-50s to wake.
const TIMEOUT_MS = 55_000;
const REVALIDATE_SECONDS = 86_400;
const META_REVALIDATE_SECONDS = 300;
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

async function fetchJson<T>(path: string, revalidate: number): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      next: { revalidate, tags: [API_CACHE_TAG] },
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

async function apiGet<T>(competition: CompetitionId, path: string): Promise<T> {
  let version: string | null = null;
  try {
    version = (await getMeta(competition)).data_version;
  } catch (error) {
    // An unreachable API fails the same way for the request itself: don't wait twice.
    if (error instanceof ApiError && error.status === null) throw error;
  }
  return fetchJson<T>(withVersion(`/api/v2/${competition}${path}`, version), REVALIDATE_SECONDS);
}

export interface MatchQuery {
  season?: number;
  team?: string;
  playoffs?: boolean;
  sort?: "latest" | "oldest";
  page?: number;
  pageSize?: number;
}

export function getMatches(competition: CompetitionId, query: MatchQuery = {}): Promise<MatchPage> {
  const params = new URLSearchParams();
  if (query.season) params.set("season", String(query.season));
  if (query.team) params.set("team", query.team);
  if (query.playoffs !== undefined) params.set("playoffs", String(query.playoffs));
  if (query.sort) params.set("sort", query.sort);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 24));
  return apiGet<MatchPage>(competition, `/matches?${params}`);
}

export function getMeta(competition: CompetitionId): Promise<Meta> {
  return fetchJson<Meta>(`/api/v2/${competition}/meta`, META_REVALIDATE_SECONDS);
}

/** Every competition of the players database, with its seasons. */
export function getCompetitions(): Promise<CompetitionList> {
  return fetchJson<CompetitionList>("/api/v2/competitions", META_REVALIDATE_SECONDS);
}

export function getTimeline(competition: CompetitionId, matchId: number): Promise<Timeline> {
  return apiGet<Timeline>(competition, `/matches/${matchId}/timeline`);
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

export function getPlayers(
  competition: CompetitionId,
  query: PlayerQuery = {},
): Promise<PlayerPage> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.role) params.set("role", query.role);
  if (query.season) params.set("season", String(query.season));
  if (query.team) params.set("team", query.team);
  if (query.sort) params.set("sort", query.sort);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 30));
  return apiGet<PlayerPage>(competition, `/players?${params}`);
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

export function getPlayer(
  competition: CompetitionId,
  playerId: string,
  window: SeasonWindow = {},
): Promise<PlayerProfile> {
  return apiGet<PlayerProfile>(
    competition,
    `/players/${encodeURIComponent(playerId)}${windowQuery(window)}`,
  );
}

/** A player's career in every competition and in all T20 cricket. */
export async function getCareers(playerId: string): Promise<PlayerCareers> {
  return fetchJson<PlayerCareers>(
    `/api/v2/players/${encodeURIComponent(playerId)}`,
    REVALIDATE_SECONDS,
  );
}

export function getPlayerSplits(
  competition: CompetitionId,
  playerId: string,
  window: SeasonWindow = {},
): Promise<PlayerSplits> {
  return apiGet<PlayerSplits>(
    competition,
    `/players/${encodeURIComponent(playerId)}/splits${windowQuery(window)}`,
  );
}

export function getSimilarPlayers(
  competition: CompetitionId,
  playerId: string,
  window: SeasonWindow = {},
): Promise<SimilarPlayers> {
  return apiGet<SimilarPlayers>(
    competition,
    `/players/${encodeURIComponent(playerId)}/similar${windowQuery(window)}`,
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

export function getMatchups(
  competition: CompetitionId,
  query: MatchupQuery = {},
): Promise<MatchupList> {
  const params = new URLSearchParams();
  if (query.batter) params.set("batter", query.batter);
  if (query.bowler) params.set("bowler", query.bowler);
  if (query.from) params.set("from", String(query.from));
  if (query.to) params.set("to", String(query.to));
  if (query.minBalls) params.set("min_balls", String(query.minBalls));
  if (query.sort) params.set("sort", query.sort);
  params.set("page", String(query.page ?? 1));
  params.set("page_size", String(query.pageSize ?? 25));
  return apiGet<MatchupList>(competition, `/matchups?${params}`);
}

export function getMatchup(
  competition: CompetitionId,
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
    competition,
    `/matchups/${encodeURIComponent(batterId)}/${encodeURIComponent(bowlerId)}${query ? `?${query}` : ""}`,
  );
}

export function getTeams(competition: CompetitionId): Promise<TeamsOverview> {
  return apiGet<TeamsOverview>(competition, "/teams");
}

export function getStandings(competition: CompetitionId, season: number): Promise<Standings> {
  return apiGet<Standings>(competition, `/teams/standings/${season}`);
}

export function getTeam(
  competition: CompetitionId,
  franchiseId: string,
  window: SeasonWindow = {},
): Promise<TeamProfile> {
  return apiGet<TeamProfile>(
    competition,
    `/teams/${encodeURIComponent(franchiseId)}${windowQuery(window)}`,
  );
}

export function getHeadToHead(
  competition: CompetitionId,
  a: string,
  b: string,
  window: SeasonWindow = {},
): Promise<HeadToHead> {
  const params = new URLSearchParams({ a, b });
  if (window.from) params.set("from", String(window.from));
  if (window.to) params.set("to", String(window.to));
  return apiGet<HeadToHead>(competition, `/teams/h2h?${params}`);
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

export function getSimSeasons(competition: CompetitionId): Promise<SimSeason[]> {
  return apiGet<SimSeason[]>(competition, "/simulate/seasons");
}

export function getSquad(
  competition: CompetitionId,
  season: number,
  franchiseId: string,
): Promise<SimSquad> {
  return apiGet<SimSquad>(
    competition,
    `/simulate/squad/${season}/${encodeURIComponent(franchiseId)}`,
  );
}

/** Ping the API so a sleeping free-tier instance starts waking before it is needed. */
export async function wakeApi(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/healthz`, {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export function simulateMatch(
  competition: CompetitionId,
  request: SimulationRequest,
): Promise<SimulationResult> {
  return apiPost<SimulationResult>(`/api/v2/${competition}/simulate/match`, request);
}

export function simulateState(
  competition: CompetitionId,
  request: StateRequest,
): Promise<StateResult> {
  return apiPost<StateResult>(`/api/v2/${competition}/simulate/state`, request);
}
