import { TeamSwatch } from "@/components/match/team-badge";
import type { FranchiseSummary, TeamRecord } from "@/lib/api/types";
import { pct, recordText } from "@/lib/teams";
import { cn } from "@/lib/utils";
import { CompetitionLink } from "@/components/competition/competition-link";
import { SeasonLabel, SeasonSpan } from "@/components/competition/season-label";

/** Win percentage as a thin bar against an even (50%) mark; the number carries the value. */
export function WinBar({
  value,
  className,
}: {
  value: number | null | undefined;
  className?: string;
}) {
  const width = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, value));
  return (
    <span
      aria-hidden="true"
      className={cn("relative block h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
    >
      <span
        className="absolute inset-y-0 left-0 rounded-full bg-primary/80"
        style={{ width: `${width}%` }}
      />
      <span className="absolute inset-y-[-2px] left-1/2 w-px bg-foreground/50" />
    </span>
  );
}

/** "148–117 · 55.8%" with a bar, for compact record cells. */
export function RecordCell({ record }: { record: TeamRecord }) {
  return (
    <span className="flex min-w-[7rem] flex-col gap-1">
      <span className="font-mono text-sm tabular-nums">
        {recordText(record)}
        <span className="text-muted-foreground"> · {pct(record.win_pct)}</span>
      </span>
      <WinBar value={record.win_pct} />
    </span>
  );
}

export function FranchiseCard({
  team,
  national = false,
}: {
  team: FranchiseSummary;
  /** National sides have no titles or playoffs: show matches and years instead. */
  national?: boolean;
}) {
  const renamed = team.names.length > 1 || team.names[0]?.name !== team.name;
  return (
    <CompetitionLink
      href={`/teams/${team.franchise_id}`}
      className="group flex flex-col gap-3 rounded-xl border border-border bg-card/70 p-4 transition-colors hover:border-primary/40 hover:bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-start gap-2">
          <TeamSwatch color={team.color} className="mt-1 size-3" />
          <span className="font-medium group-hover:text-primary">{team.name}</span>
        </span>
        <span className="font-mono text-xs text-muted-foreground">{team.franchise_id}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        <SeasonSpan first={team.first_season} last={team.last_season} />
        {" · "}
        {team.seasons}{" "}
        {national
          ? team.seasons === 1
            ? "year"
            : "years"
          : team.seasons === 1
            ? "season"
            : "seasons"}
        {renamed &&
          ` · was ${team.names
            .filter((n) => n.name !== team.name)
            .map((n) => n.name)
            .join(", ")}`}
      </p>
      <dl className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <dt className="text-muted-foreground">Won</dt>
          <dd className="font-mono text-sm tabular-nums">{pct(team.record.win_pct)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{national ? "Played" : "Titles"}</dt>
          <dd className="font-mono text-sm tabular-nums">
            {national ? team.record.played : team.titles.length}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{national ? "Years" : "Playoffs"}</dt>
          <dd className="font-mono text-sm tabular-nums">
            {national ? team.seasons : team.playoffs.length}
          </dd>
        </div>
      </dl>
      <WinBar value={team.record.win_pct} />
    </CompetitionLink>
  );
}

/** Seasons as compact chips, e.g. the years a side won the title. */
export function SeasonChips({
  seasons,
  empty = "None yet",
}: {
  seasons: number[];
  empty?: string;
}) {
  if (!seasons.length) return <span className="text-sm text-muted-foreground">{empty}</span>;
  return (
    <span className="flex flex-wrap gap-1.5">
      {seasons.map((s) => (
        <span
          key={s}
          className="rounded-md border border-border px-1.5 py-0.5 font-mono text-xs tabular-nums"
        >
          <SeasonLabel season={s} />
        </span>
      ))}
    </span>
  );
}
