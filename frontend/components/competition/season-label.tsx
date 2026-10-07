"use client";

import { useCompetition } from "@/components/competition/use-competition";
import { seasonLabel } from "@/lib/competitions";
import { seasonSpan } from "@/lib/teams";

/**
 * A season as the competition being browsed names it: 2024 in the IPL, 2023/24 in the
 * BBL. Server components render it without knowing their competition.
 */
export function SeasonLabel({ season }: { season: number }) {
  return <>{seasonLabel(useCompetition(), season)}</>;
}

/** "2008–2026" in the IPL, "2011/12–2025/26" in the BBL. */
export function SeasonSpan({ first, last }: { first: number; last: number }) {
  return <>{seasonSpan(first, last, useCompetition())}</>;
}
