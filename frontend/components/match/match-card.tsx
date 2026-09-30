import { CalendarDays, MapPin } from "lucide-react";
import Link from "next/link";

import { TeamBadge } from "@/components/match/team-badge";
import type { MatchSummary, TeamScore } from "@/lib/api/types";
import { formatDate, formatScore, stageLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

function TeamRow({ team, won }: { team: TeamScore; won: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2.5">
        <TeamBadge shortName={team.franchise_id} color={team.color} className="w-14 shrink-0" />
        <span className={cn("truncate text-sm", won ? "text-foreground" : "text-muted-foreground")}>
          {team.name}
        </span>
      </div>
      <span
        className={cn(
          "shrink-0 font-mono text-sm tabular-nums",
          won ? "font-semibold text-foreground" : "text-muted-foreground",
        )}
      >
        {formatScore(team.runs, team.wickets)}
        {team.overs && (
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">({team.overs})</span>
        )}
      </span>
    </div>
  );
}

export function MatchCard({ match, headline }: { match: MatchSummary; headline?: string }) {
  return (
    <Link
      href={`/matches/${match.match_id}`}
      className="group flex w-full flex-col gap-4 rounded-xl border border-border bg-card/70 p-4 transition-colors hover:border-primary/40 hover:bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <CalendarDays className="size-3.5" aria-hidden="true" />
          {formatDate(match.date)}
        </span>
        <span className={cn(match.is_playoff && "font-medium text-team-b")}>
          {match.season} · {stageLabel(match.stage, match.match_number)}
        </span>
      </div>
      {headline && <p className="text-sm font-medium text-balance">{headline}</p>}
      <div className="flex flex-col gap-2">
        <TeamRow team={match.team_a} won={match.winner_id === match.team_a.team_season_id} />
        <TeamRow team={match.team_b} won={match.winner_id === match.team_b.team_season_id} />
      </div>
      <div className="mt-auto flex flex-col gap-1.5 border-t border-border pt-3">
        <p className="text-xs font-medium text-foreground/90">{match.result_text}</p>
        <p className="flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">
            {match.venue.name}, {match.venue.city}
          </span>
        </p>
      </div>
    </Link>
  );
}
