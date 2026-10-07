import { TeamSwatch } from "@/components/match/team-badge";
import { ParDelta } from "@/components/players/profile-parts";
import type { MatchupListItem, MatchupPlayer } from "@/lib/api/types";
import { rate } from "@/lib/players";
import { cn } from "@/lib/utils";
import { scrollRegion } from "@/lib/a11y";
import { CompetitionLink } from "@/components/competition/competition-link";

const th = "px-3 py-2.5 text-right text-xs font-medium text-muted-foreground";
const td = "px-3 py-3 text-right font-mono tabular-nums";

function Name({ player }: { player: MatchupPlayer }) {
  return (
    <span className="inline-flex items-center gap-2">
      {player.team && <TeamSwatch color={player.team.color} />}
      {player.full_name ?? player.name}
    </span>
  );
}

/**
 * Pairs with raw, expected and shrunk strike rates. ``show`` hides the side
 * that is fixed by the filter (e.g. the batter when listing their bowlers).
 */
export function MatchupTable({
  items,
  show,
}: {
  items: MatchupListItem[];
  show: "both" | "batter" | "bowler";
}) {
  return (
    <div
      className="overflow-x-auto rounded-2xl border border-border bg-card/70"
      {...scrollRegion("Matchups")}
    >
      <table className="w-full min-w-[36rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              {show === "both" ? "Matchup" : show === "batter" ? "Batter" : "Bowler"}
            </th>
            <th scope="col" className={th}>
              Balls
            </th>
            <th scope="col" className={th}>
              Runs
            </th>
            <th scope="col" className={th}>
              Outs
            </th>
            <th scope="col" className={th}>
              SR
            </th>
            <th scope="col" className={cn(th, "hidden sm:table-cell")}>
              <abbr title="Expected from each player's overall record">Expected</abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Head-to-head strike rate shrunk towards the expectation">Estimate</abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Estimate minus expected strike rate: the matchup effect beyond form. Positive favours the batter.">
                Batter edge
              </abbr>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((m) => (
            <tr
              key={`${m.batter.player_id}-${m.bowler.player_id}`}
              className="transition-colors hover:bg-muted/40"
            >
              <th scope="row" className="px-3 py-3 text-left font-normal">
                <CompetitionLink
                  href={`/matchups?batter=${m.batter.player_id}&bowler=${m.bowler.player_id}`}
                  className="underline-offset-4 hover:text-primary hover:underline"
                >
                  {show === "both" ? (
                    <span className="flex flex-wrap items-center gap-x-2">
                      <Name player={m.batter} />
                      <span className="text-xs text-muted-foreground">vs</span>
                      <Name player={m.bowler} />
                    </span>
                  ) : (
                    <Name player={show === "batter" ? m.batter : m.bowler} />
                  )}
                </CompetitionLink>
              </th>
              <td className={cn(td, "text-muted-foreground")}>{m.balls}</td>
              <td className={td}>{m.runs}</td>
              <td className={td}>{m.dismissals}</td>
              <td className={td}>{rate(m.strike_rate, 1)}</td>
              <td className={cn(td, "hidden text-muted-foreground sm:table-cell")}>
                {rate(m.expected_strike_rate, 1)}
              </td>
              <td className={cn(td, "font-semibold")}>{rate(m.estimated_strike_rate, 1)}</td>
              <td className={td}>
                <ParDelta delta={m.edge ?? null} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
