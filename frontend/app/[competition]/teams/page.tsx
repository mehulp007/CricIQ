import type { Metadata } from "next";

import { CompetitionLink } from "@/components/competition/competition-link";
import { MatchCard } from "@/components/match/match-card";
import { TeamSwatch } from "@/components/match/team-badge";
import { Panel, StatTile } from "@/components/players/profile-parts";
import { LeagueTrendsChartLazy as LeagueTrendsChart } from "@/components/teams/league-trends-chart-lazy";
import { FranchiseCard } from "@/components/teams/parts";
import { SeasonPicker } from "@/components/teams/season-picker";
import { StandingsTable } from "@/components/teams/standings-table";
import { getStandings, getTeams } from "@/lib/api/client";
import type { Rate, TeamsOverview } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import {
  getCompetition,
  isCompetitionId,
  seasonLabel,
  type CompetitionId,
} from "@/lib/competitions";
import { parseSeason } from "@/lib/players";
import { h2hHref, pct } from "@/lib/teams";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/teams">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.label} teams`,
    description:
      competition === "ipl"
        ? "Every IPL franchise since 2008: records, titles, league tables that match the official ones, and what the toss, home ground and chasing are worth."
        : c.teamType === "national"
          ? `Every side in ${c.collective} since ${c.firstSeason}: records by year and by opponent, and what the toss, home ground and chasing are worth.`
          : `Every ${c.label} franchise since ${c.firstSeason}: records, titles, league tables and what the toss, home ground and chasing are worth.`,
  };
}

function interval(rate: Rate): string {
  return rate.low === null || rate.high === null
    ? ""
    : `90% interval ${rate.low.toFixed(1)}–${rate.high.toFixed(1)}%`;
}

// Rivalries to start from, by competition (others start from the picker).
const RIVALRIES: Partial<Record<CompetitionId, [string, string, string][]>> = {
  ipl: [
    ["MI", "CSK", "The two most successful franchises"],
    ["CSK", "RCB", "The southern derby"],
    ["MI", "KKR", "The biggest head-to-head lead"],
    ["RCB", "KKR", "The first match of the IPL"],
  ],
  t20i: [
    ["IND", "PAK", "India v Pakistan"],
    ["AUS", "ENG", "Australia v England"],
    ["IND", "AUS", "India v Australia"],
    ["NZ", "SA", "New Zealand v South Africa"],
  ],
};

// National sides with fewer matches are listed compactly.
const REGULAR_SIDE_MATCHES = 40;

function Rivalries({ competition }: { competition: CompetitionId }) {
  const pairs = RIVALRIES[competition];
  const team = getCompetition(competition).teamType === "national" ? "sides" : "franchises";
  return (
    <Panel
      id="rivalries"
      title="Head to head"
      lede={`Any two ${team}' record against each other, set against what each side's form going into those matches predicted.`}
    >
      {pairs ? (
        <ul className="grid gap-2 sm:grid-cols-2">
          {pairs.map(([a, b, why]) => (
            <li key={`${a}-${b}`}>
              <CompetitionLink
                href={h2hHref(a, b)}
                className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:border-primary/40 hover:bg-card"
              >
                <span className="font-mono font-medium">
                  {a} v {b}
                </span>
                <span className="truncate text-xs text-muted-foreground">{why}</span>
              </CompetitionLink>
            </li>
          ))}
        </ul>
      ) : (
        <CompetitionLink
          href="/teams/h2h"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Pick two {team}
        </CompetitionLink>
      )}
    </Panel>
  );
}

function Trends({
  overview,
  competition,
}: {
  overview: TeamsOverview;
  competition: CompetitionId;
}) {
  const { league } = overview;
  return (
    <Panel
      id="trends"
      title="Chasing, home ground and the toss"
      lede="The share of decided matches won by the side batting second, the home side and the toss winner, season by season. Matches at neutral venues have no home side."
    >
      <LeagueTrendsChart seasons={league.seasons} />
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          Show as a table
        </summary>
        <div className="mt-3 overflow-x-auto" {...scrollRegion("Season trends table")}>
          <table className="w-full min-w-[36rem] text-sm">
            <thead className="border-b border-border">
              <tr className="text-xs text-muted-foreground">
                <th scope="col" className="px-2 py-2 text-left font-medium">
                  Season
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Matches
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Chasing won
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Home won
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Toss winner won
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Chose to field
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Avg 1st innings
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {league.seasons.map((s) => (
                <tr key={s.season}>
                  <th scope="row" className="px-2 py-2 text-left font-normal">
                    {seasonLabel(competition, s.season)}
                  </th>
                  <td className="px-2 py-2 text-right">{s.matches}</td>
                  <td className="px-2 py-2 text-right">{pct(s.chasing_win_pct)}</td>
                  <td className="px-2 py-2 text-right">{pct(s.home_win_pct)}</td>
                  <td className="px-2 py-2 text-right">{pct(s.toss_winner_win_pct)}</td>
                  <td className="px-2 py-2 text-right">{pct(s.field_first_pct)}</td>
                  <td className="px-2 py-2 text-right">{s.avg_first_innings?.toFixed(1) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Panel>
  );
}

function LeagueStats({ overview }: { overview: TeamsOverview }) {
  const { league } = overview;
  return (
    <section aria-label="Across the competition" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Chasing side won" value={pct(league.chasing.pct)}>
        {league.chasing.total} decided matches; {interval(league.chasing)}
      </StatTile>
      {league.home.total > 0 && (
        <StatTile label="Home side won" value={pct(league.home.pct)}>
          {league.home.total} matches with a home side; {interval(league.home)}
        </StatTile>
      )}
      <StatTile label="Toss winner won" value={pct(league.toss.pct)}>
        {interval(league.toss)}: the toss is worth little
      </StatTile>
      <StatTile label="Close finishes" value={pct(league.close.pct)}>
        Won by 5 runs or fewer, with 2 balls or fewer to spare, or in a super over
      </StatTile>
    </section>
  );
}

/** National sides: no league table or champions; the sides by how much they have played. */
function NationalTeams({
  overview,
  competition,
}: {
  overview: TeamsOverview;
  competition: CompetitionId;
}) {
  const sides = [...overview.franchises].sort((a, b) => b.record.played - a.record.played);
  const regular = sides.filter((s) => s.record.played >= REGULAR_SIDE_MATCHES);
  const others = sides.filter((s) => s.record.played < REGULAR_SIDE_MATCHES);
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Teams</h1>
        <p className="max-w-3xl text-muted-foreground">
          Every side in {getCompetition(competition).collective} since{" "}
          {getCompetition(competition).firstSeason}, {sides.length} in all, from the full members to
          the newest associates. Each side&apos;s page has its record year by year and against every
          opponent.
        </p>
      </header>

      <LeagueStats overview={overview} />

      <section aria-labelledby="sides" className="flex flex-col gap-4">
        <h2 id="sides" className="text-lg font-semibold tracking-tight">
          {regular.length > 0 ? `Sides with ${REGULAR_SIDE_MATCHES} or more matches` : "Every side"}
        </h2>
        {regular.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
            {regular.map((f) => (
              <FranchiseCard key={f.franchise_id} team={f} national />
            ))}
          </div>
        )}
        {others.length > 0 && (
          <>
            {regular.length > 0 && (
              <h3 className="text-sm font-medium text-muted-foreground">Every other side</h3>
            )}
            <ul className="flex flex-wrap gap-2">
              {others.map((f) => (
                <li key={f.franchise_id}>
                  <CompetitionLink
                    href={`/teams/${f.franchise_id}`}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs transition-colors hover:border-primary/40 hover:bg-card"
                  >
                    <TeamSwatch color={f.color} />
                    {f.name}
                    <span className="font-mono text-muted-foreground tabular-nums">
                      {f.record.played}
                    </span>
                  </CompetitionLink>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <Trends overview={overview} competition={competition} />
      <Rivalries competition={competition} />
    </div>
  );
}

export default async function TeamsPage({
  params,
  searchParams,
}: PageProps<"/[competition]/teams">) {
  const competition = (await params).competition as CompetitionId;
  const c = getCompetition(competition);
  const raw = await searchParams;
  const overview = await getTeams(competition);
  if (c.teamType === "national") {
    return <NationalTeams overview={overview} competition={competition} />;
  }
  const latest = Math.max(...overview.seasons);
  const requested = parseSeason(raw.season);
  const season = requested && overview.seasons.includes(requested) ? requested : latest;
  const standings = await getStandings(competition, season);
  const active = overview.franchises.filter((f) => f.is_active);
  const former = overview.franchises.filter((f) => !f.is_active);
  const champion = overview.champions.find((ch) => ch.season === season);
  const validated = competition === "ipl";

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Teams</h1>
        <p className="max-w-3xl text-muted-foreground">
          {validated
            ? `Every IPL franchise since 2008, under every name it has played as. League tables are rebuilt from the scorecards and match the official tables for all ${overview.seasons.length} seasons, net run rate included.`
            : `Every ${c.label} franchise since ${seasonLabel(competition, c.firstSeason)}, under every name it has played as. League tables are rebuilt from the scorecards at two points a win; where the ${c.label} awarded bonus points, the official table can differ.`}
        </p>
      </header>

      <LeagueStats overview={overview} />

      <section aria-labelledby="franchises" className="flex flex-col gap-4">
        <h2 id="franchises" className="text-lg font-semibold tracking-tight">
          Franchises
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
          {active.map((f) => (
            <FranchiseCard key={f.franchise_id} team={f} />
          ))}
        </div>
        {former.length > 0 && (
          <>
            <h3 className="text-sm font-medium text-muted-foreground">Former franchises</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
              {former.map((f) => (
                <FranchiseCard key={f.franchise_id} team={f} />
              ))}
            </div>
          </>
        )}
      </section>

      <Panel
        id="table"
        title={`${seasonLabel(competition, season)} league table`}
        lede={
          <>
            Two points for a win and one for a no result; a tie settled by a super over counts as a
            win. Sides level on points are split by wins, then net run rate.
            {!validated && " Computed from the results, not the official table."}
            {standings.abandoned > 0 &&
              ` ${standings.abandoned} ${standings.abandoned === 1 ? "fixture was" : "fixtures were"} abandoned without a ball bowled and counted as no result.`}
          </>
        }
      >
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <SeasonPicker
              seasons={overview.seasons.map((s) => ({
                year: s,
                label: seasonLabel(competition, s),
              }))}
              season={season}
            />
            {champion && (
              <p className="flex items-center gap-2 text-sm">
                <TeamSwatch color={champion.champion.color} />
                <span>
                  <span className="font-medium">{champion.champion.name}</span>
                  <span className="text-muted-foreground"> won the title</span>
                </span>
              </p>
            )}
          </div>
          <StandingsTable standings={standings} />
          {standings.playoffs.length > 0 && (
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-medium">Playoffs</h3>
              <div className="grid gap-3 md:grid-cols-2">
                {standings.playoffs.map((m) => (
                  <MatchCard key={m.match_id} competition={competition} match={m} />
                ))}
              </div>
            </div>
          )}
        </div>
      </Panel>

      <Panel
        id="champions"
        title="Champions"
        lede="The final of every season. Select a season to open the replay."
      >
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {[...overview.champions].reverse().map((ch) => (
            <li key={ch.season}>
              <CompetitionLink
                href={
                  ch.final_match_id
                    ? `/matches/${ch.final_match_id}`
                    : `/teams?season=${ch.season}#table`
                }
                className="flex items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:border-primary/40 hover:bg-card"
              >
                <span className="font-mono text-muted-foreground tabular-nums">
                  {seasonLabel(competition, ch.season)}
                </span>
                <TeamSwatch color={ch.champion.color} />
                <span className="min-w-0 flex-1 truncate font-medium">{ch.champion.name}</span>
                {ch.runner_up && (
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">
                    beat {ch.runner_up.franchise_id}
                  </span>
                )}
              </CompetitionLink>
            </li>
          ))}
        </ol>
      </Panel>

      <Trends overview={overview} competition={competition} />
      <Rivalries competition={competition} />
    </div>
  );
}
