import "server-only";

import { getOnThisDay } from "@/lib/api/client";
import { COMPETITIONS, type CompetitionId } from "@/lib/competitions";
import { mergeEntries, type CalendarDay, type DatedEntry } from "@/lib/on-this-day";

export interface DayResult {
  entries: DatedEntry[];
  /** Competitions whose data could not be read (the API asleep or missing one). */
  missing: CompetitionId[];
}

/**
 * Every competition's matches on a date, merged. One competition failing never blanks the
 * page: its entries are left out and it is named in ``missing``.
 */
export async function getDay(
  date: CalendarDay,
  competitions: readonly CompetitionId[] = COMPETITIONS.map((c) => c.id),
): Promise<DayResult> {
  const results = await Promise.allSettled(
    competitions.map((id) => getOnThisDay(id, date.month, date.day)),
  );
  const lists: DatedEntry[][] = [];
  const missing: CompetitionId[] = [];
  results.forEach((result, i) => {
    const id = competitions[i];
    const c = COMPETITIONS.find((x) => x.id === id);
    if (result.status === "rejected" || !c) {
      missing.push(id);
      return;
    }
    lists.push(
      result.value.entries.map((e) => ({
        ...e,
        competition: id,
        label: c.label,
        format: c.format,
      })),
    );
  });
  return { entries: mergeEntries(lists), missing };
}
