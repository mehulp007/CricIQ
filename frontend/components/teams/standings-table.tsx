import { TeamSwatch } from "@/components/match/team-badge";
import type { Standings } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { finishLabel, formatNrr } from "@/lib/teams";
import { cn } from "@/lib/utils";
import { CompetitionLink } from "@/components/competition/competition-link";
import { SeasonLabel } from "@/components/competition/season-label";

const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
const td = "px-2 py-2.5 text-right font-mono tabular-nums";

/** A season's league table, as officially ranked: points, then wins, then net run rate. */
export function StandingsTable({ standings }: { standings: Standings }) {
  const teams = standings.rows.length;
  return (
    <div className="overflow-x-auto" {...scrollRegion(`${standings.season} league table`)}>
      <table className="w-full min-w-[40rem] text-sm">
        <caption className="sr-only">
          <SeasonLabel season={standings.season} /> league table: position, team, played, won, lost,
          no result, points, net run rate and how the season ended
        </caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "w-8 text-left")}>
              #
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              Team
            </th>
            <th scope="col" className={th}>
              <abbr title="Played" className="no-underline">
                P
              </abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Won" className="no-underline">
                W
              </abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Lost" className="no-underline">
                L
              </abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="No result" className="no-underline">
                NR
              </abbr>
            </th>
            <th scope="col" className={th}>
              Pts
            </th>
            <th scope="col" className={th}>
              <abbr title="Net run rate" className="no-underline">
                NRR
              </abbr>
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              Finish
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {standings.rows.map((r) => (
            <tr
              key={r.team.franchise_id}
              className={cn(r.finish !== "league" && "bg-primary/[0.04]")}
            >
              <td className="px-2 py-2.5 font-mono text-muted-foreground tabular-nums">
                {r.position}
              </td>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                <CompetitionLink
                  href={`/teams/${r.team.franchise_id}`}
                  className="inline-flex items-center gap-2 underline-offset-4 hover:text-primary hover:underline"
                >
                  <TeamSwatch color={r.team.color} />
                  {r.team_name}
                </CompetitionLink>
              </th>
              <td className={td}>{r.played}</td>
              <td className={td}>{r.won}</td>
              <td className={td}>{r.lost}</td>
              <td className={td}>{r.no_result}</td>
              <td className={cn(td, "font-semibold")}>{r.points}</td>
              <td className={td}>{formatNrr(r.nrr)}</td>
              <td
                className={cn(
                  "px-2 py-2.5 text-left text-xs",
                  r.finish === "champion" ? "font-medium text-primary" : "text-muted-foreground",
                )}
              >
                {r.finish === "league"
                  ? "League stage"
                  : finishLabel(r.finish, r.exit_stage, r.position, teams)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
