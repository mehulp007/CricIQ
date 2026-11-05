"use client";

import { CompetitionLink } from "@/components/competition/competition-link";
import { TeamSwatch } from "@/components/match/team-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { RankedTable } from "@/components/ui/ranked-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { BattingLeader, BowlingLeader, PhaseLeaders, PhaseSummary } from "@/lib/api/types";
import { fig } from "@/lib/phases";

function Name({ player }: { player: BattingLeader | BowlingLeader }) {
  return (
    <CompetitionLink
      href={`/players/${player.player_id}`}
      className="inline-flex max-w-[12rem] items-center gap-2 truncate underline-offset-4 hover:underline sm:max-w-none"
    >
      {player.team && <TeamSwatch color={player.team.color} />}
      <span className="truncate">{player.name}</span>
    </CompetitionLink>
  );
}

const num = (n: number) => n.toLocaleString("en-US");

/** The leading batters and bowlers in each phase, one tab per phase. */
export function PhaseLeadersTabs({
  leaders,
  phases,
  minBalls,
}: {
  leaders: PhaseLeaders[];
  phases: PhaseSummary[];
  minBalls: number;
}) {
  const label = new Map(phases.map((p) => [p.key, p.label]));
  const fallback = phases[phases.length - 1]?.key ?? "";
  return (
    <Tabs defaultValue={fallback} className="flex flex-col gap-4">
      <TabsList aria-label="Phase">
        {leaders.map((lead) => (
          <TabsTrigger key={lead.phase} value={lead.phase}>
            {label.get(lead.phase) ?? lead.phase}
          </TabsTrigger>
        ))}
      </TabsList>
      {leaders.map((lead) => {
        const name = label.get(lead.phase) ?? lead.phase;
        return (
          <TabsContent key={lead.phase} value={lead.phase} className="flex flex-col gap-6">
            {lead.batters.length === 0 && lead.bowlers.length === 0 ? (
              <EmptyState
                title="Nobody qualifies"
                description={`No player has ${num(minBalls)} balls in this phase with these filters. Lower the minimum or widen the filters.`}
              />
            ) : (
              <>
                <RankedTable
                  label={`${name}: batters`}
                  rows={lead.batters}
                  rowKey={(r) => r.player_id}
                  columns={[
                    { key: "name", header: "Batter", cell: (r) => <Name player={r} /> },
                    {
                      key: "innings",
                      header: "Inns",
                      cell: (r) => num(r.innings),
                      numeric: true,
                      wide: true,
                    },
                    { key: "balls", header: "Balls", cell: (r) => num(r.balls), numeric: true },
                    { key: "runs", header: "Runs", cell: (r) => num(r.runs), numeric: true },
                    { key: "sr", header: "SR", cell: (r) => fig(r.strike_rate), numeric: true },
                    {
                      key: "outs",
                      header: "Outs",
                      cell: (r) => num(r.outs),
                      numeric: true,
                      wide: true,
                    },
                    {
                      key: "avg",
                      header: "Avg",
                      cell: (r) => fig(r.average),
                      numeric: true,
                      wide: true,
                    },
                    {
                      key: "boundary",
                      header: "Boundary %",
                      cell: (r) => fig(r.boundary_pct, 1),
                      numeric: true,
                    },
                  ]}
                />
                <RankedTable
                  label={`${name}: bowlers`}
                  rows={lead.bowlers}
                  rowKey={(r) => r.player_id}
                  columns={[
                    { key: "name", header: "Bowler", cell: (r) => <Name player={r} /> },
                    {
                      key: "innings",
                      header: "Inns",
                      cell: (r) => num(r.innings),
                      numeric: true,
                      wide: true,
                    },
                    { key: "balls", header: "Balls", cell: (r) => num(r.balls), numeric: true },
                    { key: "wickets", header: "Wkts", cell: (r) => num(r.wickets), numeric: true },
                    { key: "econ", header: "Econ", cell: (r) => fig(r.economy), numeric: true },
                    {
                      key: "sr",
                      header: "SR",
                      cell: (r) => fig(r.strike_rate, 1),
                      numeric: true,
                      wide: true,
                    },
                    { key: "dot", header: "Dot %", cell: (r) => fig(r.dot_pct, 1), numeric: true },
                  ]}
                />
              </>
            )}
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
