import { featuredBundles } from "@/data/featured";
import type { CompetitionId } from "@/lib/competitions";

import type { MatchSummary, Timeline } from "./api/types";

/**
 * Featured replays are bundled with the app (exported from the API's own
 * serializer), so they load instantly and never depend on the API being awake.
 * Each competition has its own (`data/featured/<competition>/`).
 */
export interface FeaturedMatch {
  match_id: number;
  headline: string;
  summary: MatchSummary;
}

interface FeaturedIndex {
  data_version: string;
  matches: FeaturedMatch[];
}

export interface SeasonLeader {
  player_id: string;
  name: string;
  team: string | null;
  value: number;
  detail: string;
}

/** The latest season at a glance, exported with the featured replays. */
export interface SeasonSnapshot {
  season: number;
  label: string;
  matches: number;
  champion: string | null;
  first_innings_average: number;
  previous_first_innings_average: number | null;
  sixes: number;
  leaders: Record<"runs" | "wickets" | "runs_above_par" | "runs_saved", SeasonLeader>;
}

function bundle(competition: CompetitionId) {
  const found = featuredBundles[competition];
  if (!found) throw new Error(`no featured replays for ${competition}`);
  return found;
}

export function featuredMatches(competition: CompetitionId): readonly FeaturedMatch[] {
  return (bundle(competition).index as FeaturedIndex).matches;
}

export function seasonSnapshot(competition: CompetitionId): SeasonSnapshot {
  return bundle(competition).snapshot as SeasonSnapshot;
}

/** The data version the bundled replays were exported from (the same for every competition). */
export function dataVersion(competition: CompetitionId = "ipl"): string {
  return (bundle(competition).index as FeaturedIndex).data_version;
}

export function isFeatured(competition: CompetitionId, matchId: number): boolean {
  return matchId in bundle(competition).timelines;
}

export async function loadFeaturedTimeline(
  competition: CompetitionId,
  matchId: number,
): Promise<Timeline | null> {
  const load = bundle(competition).timelines[matchId];
  return load ? load() : null;
}
