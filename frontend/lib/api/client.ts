import "server-only";

import type { MatchPage, Meta, Timeline } from "./types";

/**
 * Server-side client for the CricIQ API. Historical data only changes when the
 * API is redeployed, so responses are cached by Next.js for a day.
 */
const API_URL = process.env.CRICIQ_API_URL ?? "http://localhost:8000";

// The free-tier API sleeps when idle and can take ~30-50s to wake.
const TIMEOUT_MS = 55_000;
const REVALIDATE_SECONDS = 86_400;

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
      next: { revalidate: REVALIDATE_SECONDS },
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
