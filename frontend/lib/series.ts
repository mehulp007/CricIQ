/**
 * Series and tournaments (Tests, ODIs, T20Is): titles, dates and how major
 * tournaments group into editions. The scores and results come from the API.
 */
import type { SeriesSummary } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

/** "The Ashes 2005", "Men's Cricket World Cup 2023". */
export function seriesTitle(s: Pick<SeriesSummary, "name" | "season">): string {
  return s.name.includes(s.season) ? s.name : `${s.name} ${s.season}`;
}

/** "21 Jul 2005 – 12 Sep 2005", or one date for a one-day event. */
export function dateRange(start: string, end: string): string {
  return start === end ? formatDate(start) : `${formatDate(start)} – ${formatDate(end)}`;
}

/** "5-Test series" (counting matches the data is missing), "One ODI", "Tournament". */
export function kindLabel(
  s: Pick<SeriesSummary, "kind" | "matches" | "missing">,
  format: string,
): string {
  if (s.kind === "tournament") return "Tournament";
  const noun = format === "Test" ? "Test" : format === "ODI" ? "ODI" : "T20I";
  const length = s.matches + s.missing;
  return length === 1 ? `One ${noun}` : `${length}-${noun} series`;
}

export interface TournamentEditions {
  id: string;
  name: string;
  editions: SeriesSummary[];
}

/** The major tournaments' order on the series page: World Cups first. */
const TOURNAMENT_ORDER = [
  "cricket-world-cup",
  "t20-world-cup",
  "world-test-championship-final",
  "champions-trophy",
  "asia-cup-odi",
  "asia-cup-t20i",
];

function rank(id: string): number {
  const found = TOURNAMENT_ORDER.indexOf(id);
  return found === -1 ? TOURNAMENT_ORDER.length : found;
}

/** Major tournaments, each with its editions newest first, World Cups first. */
export function groupTournaments(items: SeriesSummary[]): TournamentEditions[] {
  const found = new Map<string, TournamentEditions>();
  for (const s of items) {
    if (!s.tournament_id) continue;
    const entry = found.get(s.tournament_id) ?? { id: s.tournament_id, name: s.name, editions: [] };
    entry.editions.push(s);
    found.set(s.tournament_id, entry);
  }
  for (const entry of found.values()) {
    entry.editions.sort((a, b) => b.start_date.localeCompare(a.start_date));
  }
  return [...found.values()].sort(
    (a, b) => rank(a.id) - rank(b.id) || a.name.localeCompare(b.name),
  );
}

/** Notes a series page owes its reader: unfinished, incomplete or unnamed. */
export function seriesNotes(s: SeriesSummary): string[] {
  const notes: string[] = [];
  if (s.recent) {
    notes.push(
      "The last match was within two weeks of the latest data update, so more matches may follow.",
    );
  }
  if (s.missing > 0) {
    notes.push(
      `${s.missing === 1 ? "One match" : `${s.missing} matches`} of this series ${s.missing === 1 ? "is" : "are"} not in the data (often a match abandoned without a ball bowled), so the score counts the matches played.`,
    );
  }
  if (!s.named) {
    notes.push(
      "Cricsheet names no series for these matches; they are grouped by the two sides and their dates.",
    );
  }
  return notes;
}

/** "won 5" / "1 win" style counts for a side in a tournament. */
export function winsLabel(wins: number): string {
  return `${wins} ${wins === 1 ? "win" : "wins"}`;
}
