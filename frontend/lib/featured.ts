import index from "@/data/featured/index.json";
import { featuredTimelines } from "@/data/featured/manifest";

import type { MatchSummary, Timeline } from "./api/types";

/**
 * Featured replays are bundled with the app (exported from the API's own
 * serializer), so they load instantly and never depend on the API being awake.
 */
export interface FeaturedMatch {
  match_id: number;
  headline: string;
  summary: MatchSummary;
}

export const FEATURED: readonly FeaturedMatch[] = index.matches as FeaturedMatch[];

export const DATA_VERSION: string = index.data_version;

export function isFeatured(matchId: number): boolean {
  return matchId in featuredTimelines;
}

export async function loadFeaturedTimeline(matchId: number): Promise<Timeline | null> {
  const load = featuredTimelines[matchId];
  return load ? load() : null;
}

/** Season range covered by the data, e.g. "2008–2026". */
export function seasonRange(): string {
  const seasons = FEATURED.map((m) => m.summary.season);
  return `${Math.min(...seasons)}–${Math.max(...seasons)}`;
}
