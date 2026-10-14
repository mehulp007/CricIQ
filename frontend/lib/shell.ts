import "server-only";

import { COMPETITIONS, seasonLabel, type CompetitionId } from "@/lib/competitions";
import { seasonSnapshot } from "@/lib/featured";

/** What the competition switcher shows for each competition: small, computed on the server. */
export interface CompetitionCard {
  id: CompetitionId;
  label: string;
  name: string;
  group: "Leagues" | "Internationals";
  /** "T20 · 2008–2026" */
  detail: string;
}

export function competitionCards(): CompetitionCard[] {
  return COMPETITIONS.map((c) => ({
    id: c.id,
    label: c.label,
    name: c.name,
    group: c.teamType === "club" ? "Leagues" : "Internationals",
    detail: `${c.format} · ${seasonLabel(c.id, c.firstSeason)}–${seasonSnapshot(c.id).label}`,
  }));
}
