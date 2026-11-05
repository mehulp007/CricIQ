import Link from "next/link";

import { TeamSwatch } from "@/components/match/team-badge";
import { competitionPath } from "@/lib/competitions";
import type { DatedEntry } from "@/lib/on-this-day";
import { cn } from "@/lib/utils";

const link =
  "text-primary underline underline-offset-4 decoration-primary/40 hover:decoration-primary";

/** One match on the day: when, the standout figure, the result and where to go next. */
export function EntryCard({ entry, hero = false }: { entry: DatedEntry; hero?: boolean }) {
  const match = competitionPath(entry.competition, `/matches/${entry.match_id}`);
  const stage = entry.stage && entry.stage !== "League" ? entry.stage : null;
  const { highlight, swing } = entry;
  return (
    <article
      aria-labelledby={`entry-${entry.competition}-${entry.match_id}`}
      className={cn(
        "flex h-full min-w-0 flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-elev-1",
        hero && "gap-4 p-6 sm:p-8",
      )}
    >
      <p className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
        {entry.year} · {entry.label}
        {stage && ` · ${stage}`}
      </p>
      <div className="flex items-start justify-between gap-4">
        <h3
          id={`entry-${entry.competition}-${entry.match_id}`}
          className={cn(
            "min-w-0 font-semibold tracking-tight",
            hero ? "text-title sm:text-2xl" : "text-base",
          )}
        >
          {entry.headline}
        </h3>
        {highlight && (
          <p className="shrink-0 text-right">
            <span
              className={cn(
                "block font-mono font-semibold tabular-nums",
                hero ? "text-4xl sm:text-5xl" : "text-2xl",
              )}
            >
              {highlight.figure}
            </span>
            <span className="text-xs text-muted-foreground">{highlight.detail}</span>
          </p>
        )}
      </div>
      <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          {entry.teams.map((t, i) => (
            <span key={t.franchise_id} className="inline-flex items-center gap-1.5">
              {i > 0 && <span>v</span>}
              <TeamSwatch color={t.color} />
              <span className="text-foreground">{t.name}</span>
            </span>
          ))}
        </span>
        <span aria-hidden="true">·</span>
        <span>{entry.result}</span>
      </p>
      {swing && swing.team && (
        <p className="text-sm">
          <span className="text-muted-foreground">Biggest swing: </span>
          one ball moved {swing.team.name}&apos;s chance of winning from {swing.before.toFixed(0)}%
          to {swing.after.toFixed(0)}%{" "}
          <span className="text-xs text-muted-foreground">(model estimate)</span>
        </p>
      )}
      <p className="mt-auto flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <Link href={match} className={link} prefetch={false}>
          Scorecard and replay
        </Link>
        {swing && (
          <Link href={`${match}?ball=${swing.ball}`} className={link} prefetch={false}>
            Replay that ball
          </Link>
        )}
        {highlight && (
          <Link
            href={competitionPath(entry.competition, `/players/${highlight.player_id}`)}
            className={link}
            prefetch={false}
          >
            {highlight.name}
          </Link>
        )}
      </p>
    </article>
  );
}
