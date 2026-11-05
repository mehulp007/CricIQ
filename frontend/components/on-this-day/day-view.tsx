import { CalendarDays, Download } from "lucide-react";
import Link from "next/link";

import { DatePicker } from "@/components/on-this-day/date-picker";
import { EntryCard } from "@/components/on-this-day/entry-card";
import { EntryList } from "@/components/on-this-day/entry-list";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar, type FilterField } from "@/components/ui/filter-bar";
import { PageHeader } from "@/components/ui/page-header";
import type { DayResult } from "@/lib/api/on-this-day";
import { COMPETITIONS } from "@/lib/competitions";
import { dateSlug, dayLabel, filterEntries, shiftDay, type CalendarDay } from "@/lib/on-this-day";

type Raw = Record<string, string | string[] | undefined>;
const one = (raw: Raw, key: string) => {
  const value = raw[key];
  return (Array.isArray(value) ? value[0] : value) || undefined;
};

const FORMATS = [
  { value: "T20", label: "T20" },
  { value: "ODI", label: "ODIs" },
  { value: "Test", label: "Tests" },
];

/** A day's page: the most notable match, then every other one, with filters and the days around. */
export function DayView({
  date,
  result,
  raw,
  today,
}: {
  date: CalendarDay;
  result: DayResult;
  raw: Raw;
  /** Shown as today's page (the date a visitor lands on). */
  today: boolean;
}) {
  const filters = {
    competition: one(raw, "competition"),
    format: one(raw, "format"),
    team: one(raw, "team"),
  };
  const entries = filterEntries(result.entries, filters);
  const teams = [...new Set(result.entries.flatMap((e) => e.teams.map((t) => t.name)))].sort();
  const fields: FilterField[] = [
    {
      param: "competition",
      label: "Competition",
      all: "All competitions",
      choices: COMPETITIONS.map((c) => ({ value: c.id, label: c.label })),
      width: "w-44",
    },
    { param: "format", label: "Format", all: "All formats", choices: FORMATS, width: "w-36" },
    {
      param: "team",
      label: "Side",
      all: "Any side",
      choices: teams.map((t) => ({ value: t, label: t })),
      width: "w-52",
    },
  ];
  const [hero, ...rest] = entries;
  const previous = shiftDay(date, -1);
  const next = shiftDay(date, 1);
  const label = dayLabel(date);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="The cricket calendar"
        title={`On this day: ${label}`}
        description={`Matches played on ${label} in every year of CricIQ's data, across the IPL, BBL, PSL, CPL, SA20, T20Is, ODIs and Tests: the standout performance, the result and the ball that moved the result most.`}
        actions={
          <a
            href={`/on-this-day/${dateSlug(date)}/card`}
            download={`criciq-on-this-day-${dateSlug(date)}.png`}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:border-primary/40"
          >
            <Download className="size-4" aria-hidden="true" />
            Download this card
          </a>
        }
      />
      <nav aria-label="Dates" className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <Link
          href={`/on-this-day/${dateSlug(previous)}`}
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          <span aria-hidden="true">← </span>
          {dayLabel(previous)}
        </Link>
        {!today && (
          <Link
            href="/on-this-day"
            className="text-sm text-primary underline-offset-4 hover:underline"
          >
            Today
          </Link>
        )}
        <Link
          href={`/on-this-day/${dateSlug(next)}`}
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          {dayLabel(next)}
          <span aria-hidden="true"> →</span>
        </Link>
        <DatePicker date={date} />
      </nav>
      <FilterBar fields={fields} />
      {result.missing.length > 0 && (
        <p className="text-sm text-muted-foreground" role="status">
          Some competitions could not be read just now (
          {result.missing.map((id) => COMPETITIONS.find((c) => c.id === id)?.label).join(", ")});
          their matches are left out.
        </p>
      )}
      {hero ? (
        <>
          <section aria-label="The day's standout match">
            <EntryCard entry={hero} hero />
          </section>
          {rest.length > 0 && (
            <section aria-labelledby="more-heading" className="flex flex-col gap-4">
              <h2 id="more-heading" className="text-lg font-semibold tracking-tight">
                Also on {label}
              </h2>
              <EntryList entries={rest} />
            </section>
          )}
        </>
      ) : (
        <EmptyState
          icon={CalendarDays}
          title={`No matches on ${label}`}
          description={
            result.entries.length > 0
              ? "None match these filters. Try all competitions or any side."
              : "No match in CricIQ's data was played on this date. Try the day before or after."
          }
        />
      )}
      <p className="text-xs text-muted-foreground">
        Ranked by what made the match stand out: a final or playoff, a hundred or fifty, a five- or
        four-wicket haul, and a single ball that moved a side&apos;s chance of winning by 50 points
        or more (a model estimate).
      </p>
    </div>
  );
}
