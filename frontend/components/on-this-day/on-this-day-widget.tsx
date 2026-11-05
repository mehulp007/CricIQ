"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EntryCard } from "@/components/on-this-day/entry-card";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import type { CompetitionId } from "@/lib/competitions";
import { dateSlug, dayLabel, todayIn, type CalendarDay, type DatedEntry } from "@/lib/on-this-day";

interface Day {
  date: CalendarDay;
  entries: DatedEntry[];
  total: number;
}

/**
 * The most notable match played on the visitor's own date in past years (across every
 * competition, or one). Fetched in the browser, so the page itself stays static; left out
 * when the day has no match or the API is asleep.
 */
export function OnThisDayWidget({ competition }: { competition?: CompetitionId }) {
  const [day, setDay] = useState<Day | null | undefined>(undefined);

  useEffect(() => {
    const own = todayIn(Intl.DateTimeFormat().resolvedOptions().timeZone);
    const query = new URLSearchParams({ date: dateSlug(own) });
    if (competition) query.set("competition", competition);
    let live = true;
    fetch(`/api/on-this-day?${query}`)
      .then((r) => (r.ok ? (r.json() as Promise<Day>) : null))
      .then((found) => live && setDay(found && found.entries.length > 0 ? found : null))
      .catch(() => live && setDay(null));
    return () => {
      live = false;
    };
  }, [competition]);

  if (day === null) return null;
  const label = day ? dayLabel(day.date) : null;
  return (
    <section aria-labelledby="on-this-day-heading" className="flex flex-col gap-6">
      <SectionHeader
        id="on-this-day-heading"
        title="On this day"
        description={
          label
            ? `Played on ${label} in a past year${day && day.total > 1 ? `, one of ${day.total} matches on the date` : ""}.`
            : "Played on today's date in a past year."
        }
        action={
          day && (
            <Link
              href={`/on-this-day/${dateSlug(day.date)}`}
              className="text-primary underline-offset-4 hover:underline"
            >
              Every match on {label}
            </Link>
          )
        }
      />
      {day ? (
        <EntryCard entry={day.entries[0]} />
      ) : (
        <Skeleton className="h-44 rounded-2xl border border-border" />
      )}
    </section>
  );
}
