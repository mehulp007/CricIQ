import { CompetitionLink } from "@/components/competition/competition-link";
import { TeamSwatch } from "@/components/match/team-badge";
import type { RecordLeader } from "@/lib/api/types";
import { CARD_LINK } from "@/lib/card";
import { shortDate, whoLabel } from "@/lib/records";
import { cn } from "@/lib/utils";

/** One record on the hub: its figure, who holds it and where, linking to the full list. */
export function RecordCard({ leader }: { leader: RecordLeader }) {
  const { record } = leader;
  const top = leader.leaders[0];
  const more = leader.tied_count - 1;
  const when = [top.opponent ? `v ${top.opponent.name}` : null, shortDate(top.date)]
    .filter(Boolean)
    .join(" · ");
  return (
    <CompetitionLink
      href={`/records/${record.key}`}
      className={cn(CARD_LINK, "flex h-full min-w-0 flex-col gap-2 p-4")}
      aria-label={`${record.label}: ${top.display}, ${whoLabel(top)}`}
      // The hub has about 35 of these: prefetching each would run its record's query.
      prefetch={false}
    >
      <span className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        {record.label}
        {record.model && <span className="ml-1.5 normal-case">· Model estimate</span>}
      </span>
      <span className="font-mono text-2xl font-semibold tracking-tight tabular-nums">
        {top.display}
      </span>
      <span className="flex min-w-0 items-center gap-2 text-sm">
        {top.team && <TeamSwatch color={top.team.color} />}
        <span className="truncate">{whoLabel(top)}</span>
      </span>
      {(when || more > 0) && (
        <span className="truncate text-xs text-muted-foreground">
          {when}
          {more > 0 && `${when ? " · " : ""}and ${more} more`}
        </span>
      )}
    </CompetitionLink>
  );
}
