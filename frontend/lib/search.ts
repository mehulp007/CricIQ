/**
 * The search palette's matching: pages, competitions, teams and featured replays are matched here
 * on the client (players are searched by the API as you type).
 */

export type ResultGroup = "Pages" | "Competitions" | "Players" | "Teams" | "Featured replays";

export const GROUP_ORDER: readonly ResultGroup[] = [
  "Pages",
  "Competitions",
  "Players",
  "Teams",
  "Featured replays",
];

export interface SearchResult {
  /** Unique across groups. */
  id: string;
  group: ResultGroup;
  label: string;
  detail?: string;
  href: string;
  /** For teams: their colour swatch. */
  color?: string;
}

// Accents do not matter: "Muller" finds "Müller". NFD splits letters from their marks (\p{M}).
const normalise = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

/**
 * How well `text` matches `query`, or null for no match. Every query word must start a word of the
 * text (so "kol kn" finds "Kolkata Knight Riders"); a match at the very start ranks highest.
 */
export function matchScore(query: string, text: string): number | null {
  const q = normalise(query).trim();
  if (!q) return 0;
  const haystack = normalise(text);
  const words = haystack.split(/[^a-z0-9]+/).filter(Boolean);
  let score = 0;
  for (const part of q.split(/\s+/)) {
    const at = words.findIndex((w) => w.startsWith(part));
    if (at === -1) return null;
    score += at === 0 ? 3 : 1;
  }
  if (haystack.startsWith(q)) score += 5;
  return score;
}

/** The results of one group that match, best first; all of them (in order) for an empty query. */
export function filterResults(query: string, results: readonly SearchResult[]): SearchResult[] {
  if (!query.trim()) return [...results];
  return results
    .map((r) => ({ r, score: matchScore(query, `${r.label} ${r.detail ?? ""}`) }))
    .filter((x): x is { r: SearchResult; score: number } => x.score !== null)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.r);
}

/** Results in display order, grouped, each group capped. */
export function groupResults(
  results: readonly SearchResult[],
  perGroup = 6,
): { group: ResultGroup; items: SearchResult[] }[] {
  return GROUP_ORDER.map((group) => ({
    group,
    items: results.filter((r) => r.group === group).slice(0, perGroup),
  })).filter((g) => g.items.length > 0);
}
