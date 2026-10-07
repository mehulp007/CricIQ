import { TeamBadge } from "@/components/match/team-badge";
import type { PlayerListItem } from "@/lib/api/types";
import { rate, roleLabel } from "@/lib/players";
import { cn } from "@/lib/utils";
import { CompetitionLink } from "@/components/competition/competition-link";

const th = "px-3 py-2.5 text-right text-xs font-medium text-muted-foreground";
const td = "px-3 py-3 text-right font-mono tabular-nums";

/** Directory rows. Numbers are scoped to the active season and team filters. */
export function PlayerTable({ players }: { players: PlayerListItem[] }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card/70">
      <table className="w-full text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Player
            </th>
            <th scope="col" className={cn(th, "hidden text-left md:table-cell")}>
              Team
            </th>
            <th scope="col" className={cn(th, "hidden lg:table-cell")}>
              Seasons
            </th>
            <th scope="col" className={th}>
              <abbr title="Matches" className="no-underline">
                M
              </abbr>
            </th>
            <th scope="col" className={th}>
              Runs
            </th>
            <th scope="col" className={cn(th, "hidden sm:table-cell")}>
              <abbr title="Batting average" className="no-underline">
                Avg
              </abbr>
            </th>
            <th scope="col" className={cn(th, "hidden sm:table-cell")}>
              <abbr title="Strike rate" className="no-underline">
                SR
              </abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Wickets" className="no-underline">
                Wkts
              </abbr>
            </th>
            <th scope="col" className={cn(th, "hidden sm:table-cell")}>
              <abbr title="Economy rate" className="no-underline">
                Econ
              </abbr>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {players.map((p) => (
            <tr key={p.player_id} className="transition-colors hover:bg-muted/40">
              <th scope="row" className="px-3 py-3 text-left font-normal">
                <CompetitionLink
                  href={`/players/${p.player_id}`}
                  className="font-medium underline-offset-4 hover:text-primary hover:underline"
                >
                  {p.full_name ?? p.name}
                </CompetitionLink>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  {roleLabel(p.role, p.is_keeper)}
                  {p.country && ` · ${p.country}`}
                  {p.team && <span className="md:hidden"> · {p.team.franchise_id}</span>}
                </span>
              </th>
              <td className="hidden px-3 py-3 md:table-cell">
                {p.team && <TeamBadge shortName={p.team.franchise_id} color={p.team.color} />}
              </td>
              <td className={cn(td, "hidden text-muted-foreground lg:table-cell")}>
                {p.first_season === p.last_season
                  ? p.first_season
                  : `${p.first_season}–${p.last_season}`}
              </td>
              <td className={td}>{p.matches}</td>
              <td className={cn(td, "font-semibold")}>{p.runs}</td>
              <td className={cn(td, "hidden text-muted-foreground sm:table-cell")}>
                {rate(p.batting_average)}
              </td>
              <td className={cn(td, "hidden text-muted-foreground sm:table-cell")}>
                {rate(p.strike_rate)}
              </td>
              <td className={cn(td, "font-semibold")}>{p.wickets}</td>
              <td className={cn(td, "hidden text-muted-foreground sm:table-cell")}>
                {rate(p.economy)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
