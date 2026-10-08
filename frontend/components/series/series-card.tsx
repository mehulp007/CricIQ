import { CalendarDays, Trophy } from "lucide-react";
import Link from "next/link";

import { TeamSwatch } from "@/components/match/team-badge";
import type { SeriesSummary } from "@/lib/api/types";
import { competitionPath, getCompetition, type CompetitionId } from "@/lib/competitions";
import { dateRange, kindLabel, seriesTitle } from "@/lib/series";
import { cn } from "@/lib/utils";

/** One series or tournament: its sides, dates and result, linking to its page. */
export function SeriesCard({
  competition,
  series,
}: {
  competition: CompetitionId;
  series: SeriesSummary;
}) {
  const format = getCompetition(competition).format;
  const sides = series.kind === "series" ? series.teams : series.teams.slice(0, 6);
  return (
    <Link
      href={competitionPath(competition, `/series/${series.event_id}`)}
      className="group flex w-full flex-col gap-3 rounded-xl border border-border bg-card/70 p-4 transition-colors hover:border-primary/40 hover:bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <CalendarDays className="size-3.5" aria-hidden="true" />
          {dateRange(series.start_date, series.end_date)}
        </span>
        <span className={cn(series.tournament_id && "font-medium text-team-b")}>
          {kindLabel(series, format)}
        </span>
      </div>
      <p className="flex items-start gap-2 font-medium text-balance group-hover:text-primary">
        {series.tournament_id && (
          <Trophy className="mt-1 size-3.5 shrink-0 text-team-b" aria-hidden="true" />
        )}
        {seriesTitle(series)}
      </p>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {sides.map((t) => (
          <li key={t.franchise_id} className="flex items-center gap-1.5">
            <TeamSwatch color={t.color} />
            <span>{t.name}</span>
            {series.kind === "series" && (
              <span className="font-mono text-foreground tabular-nums">{t.wins}</span>
            )}
          </li>
        ))}
        {series.teams.length > sides.length && <li>+{series.teams.length - sides.length} more</li>}
      </ul>
      <p className="mt-auto border-t border-border pt-3 text-xs font-medium text-foreground/90">
        {series.result_text}
      </p>
    </Link>
  );
}
