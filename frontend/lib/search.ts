/**
 * The search palette's matching: pages, competitions, teams, record lists, dates and featured
 * replays are matched here on the client (players are searched by the API as you type).
 */

import { dateSlug } from "@/lib/on-this-day";
import { noteDateLabel } from "@/lib/notes";

export type ResultGroup =
  "Pages" | "Competitions" | "Players" | "Teams" | "Records" | "Days" | "Featured replays";

export const GROUP_ORDER: readonly ResultGroup[] = [
  "Pages",
  "Competitions",
  "Days",
  "Players",
  "Teams",
  "Records",
  "Featured replays",
];

const MONTH_NAMES = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
];

export interface DateQuery {
  month: number;
  day: number;
  year: number | null;
}

function month(word: string): number | null {
  if (word.length < 3) return null;
  const found = MONTH_NAMES.findIndex((m) => m.startsWith(word.toLowerCase()));
  return found === -1 ? null : found + 1;
}

function real({ month: m, day, year }: DateQuery): boolean {
  // A leap year, so 29 February is a day for On this day.
  const probe = new Date(Date.UTC(year ?? 2024, m - 1, day));
  return probe.getUTCMonth() === m - 1 && probe.getUTCDate() === day;
}

/** A date in a query: "2024-04-15", "15 April 2024", "April 15, 2024", "15 apr" (no year). */
export function parseDateQuery(query: string): DateQuery | null {
  const q = query.trim().toLowerCase().replace(/,/g, " ").replace(/\s+/g, " ");
  let found: DateQuery | null = null;
  let match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(q);
  if (match) found = { year: +match[1], month: +match[2], day: +match[3] };
  match = found ? null : /^(\d{1,2})(?:st|nd|rd|th)? ([a-z]+)(?: (\d{4}))?$/.exec(q);
  if (match && month(match[2])) {
    found = { day: +match[1], month: month(match[2])!, year: match[3] ? +match[3] : null };
  }
  match = found ? null : /^([a-z]+) (\d{1,2})(?:st|nd|rd|th)?(?: (\d{4}))?$/.exec(q);
  if (match && month(match[1])) {
    found = { day: +match[2], month: month(match[1])!, year: match[3] ? +match[3] : null };
  }
  return found && found.month >= 1 && found.month <= 12 && real(found) ? found : null;
}

/** The pages a date query leads to: that day in past years, and its daily note if one exists. */
export function dateResults(query: string, noteDates: ReadonlySet<string> | null): SearchResult[] {
  const date = parseDateQuery(query);
  if (!date) return [];
  const slug = dateSlug({ month: date.month, day: date.day });
  const label = `${date.day} ${MONTH_NAMES[date.month - 1][0].toUpperCase()}${MONTH_NAMES[date.month - 1].slice(1)}`;
  const results: SearchResult[] = [
    {
      id: `day:${slug}`,
      group: "Days",
      label: `On this day: ${label}`,
      detail: "Matches on the date in past years",
      href: `/on-this-day/${slug}`,
    },
  ];
  if (date.year !== null) {
    const iso = `${date.year}-${String(date.month).padStart(2, "0")}-${String(date.day).padStart(2, "0")}`;
    if (noteDates?.has(iso)) {
      results.unshift({
        id: `note:${iso}`,
        group: "Days",
        label: `Daily note: ${noteDateLabel(iso)}`,
        detail: "What happened that day",
        href: `/notes/${iso}`,
      });
    }
  }
  return results;
}

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
