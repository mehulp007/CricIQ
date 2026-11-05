/**
 * On This Day helpers: calendar dates as URL slugs ("november-5"), today's date in a time
 * zone, the days either side (29 February included), and every competition's entries for a
 * date merged into one list.
 */

import type { DayEntry } from "@/lib/api/types";
import type { CompetitionId, MatchFormat } from "@/lib/competitions";

export const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

/** The site's own time zone: its "today" until the visitor's browser says otherwise. */
export const HOME_TIME_ZONE = "Asia/Kolkata";

export interface CalendarDay {
  month: number; // 1-12
  day: number;
}

/** Days in a month of a leap year, so 29 February is a date like any other. */
export function daysIn(month: number): number {
  return new Date(Date.UTC(2024, month, 0)).getUTCDate();
}

/** "november-5". */
export function dateSlug({ month, day }: CalendarDay): string {
  return `${MONTHS[month - 1].toLowerCase()}-${day}`;
}

/** The date a slug names, or null ("november-31" and "smarch-1" are not dates). */
export function parseDateSlug(slug: string): CalendarDay | null {
  const match = /^([a-z]+)-(\d{1,2})$/.exec(slug.toLowerCase());
  if (!match) return null;
  const month = MONTHS.findIndex((m) => m.toLowerCase() === match[1]) + 1;
  const day = Number(match[2]);
  if (month === 0 || day < 1 || day > daysIn(month)) return null;
  return { month, day };
}

/** "5 November". */
export function dayLabel({ month, day }: CalendarDay): string {
  return `${day} ${MONTHS[month - 1]}`;
}

/** The calendar day of ``now`` in ``timeZone``. */
export function todayIn(timeZone: string, now: Date = new Date()): CalendarDay {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    month: "numeric",
    day: "numeric",
  }).formatToParts(now);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return { month: get("month"), day: get("day") };
}

/** The day before (-1) or after (+1), round the year (31 December is followed by 1 January). */
export function shiftDay({ month, day }: CalendarDay, by: -1 | 1): CalendarDay {
  if (by === 1) {
    if (day < daysIn(month)) return { month, day: day + 1 };
    return { month: month === 12 ? 1 : month + 1, day: 1 };
  }
  if (day > 1) return { month, day: day - 1 };
  const previous = month === 1 ? 12 : month - 1;
  return { month: previous, day: daysIn(previous) };
}

/** Every date of the (leap) year, for the sitemap. */
export function allDays(): CalendarDay[] {
  return MONTHS.flatMap((_, i) =>
    Array.from({ length: daysIn(i + 1) }, (_, d) => ({ month: i + 1, day: d + 1 })),
  );
}

/** An entry with the competition it came from. */
export interface DatedEntry extends DayEntry {
  competition: CompetitionId;
  label: string;
  format: MatchFormat;
}

/** One list from every competition's entries: most notable first, then the most recent. */
export function mergeEntries(lists: DatedEntry[][]): DatedEntry[] {
  return lists
    .flat()
    .sort(
      (a, b) =>
        b.notability - a.notability || b.date.localeCompare(a.date) || a.match_id - b.match_id,
    );
}

/** Entries narrowed to a competition, a format and a side (by name, across competitions). */
export function filterEntries(
  entries: DatedEntry[],
  { competition, format, team }: { competition?: string; format?: string; team?: string },
): DatedEntry[] {
  return entries.filter(
    (e) =>
      (!competition || e.competition === competition) &&
      (!format || e.format === format) &&
      (!team || e.teams.some((t) => t.name === team)),
  );
}
