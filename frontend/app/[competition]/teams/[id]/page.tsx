import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Panel, StatTile } from "@/components/players/profile-parts";
import { SeasonWindow } from "@/components/players/season-window";
import { RecordCell, SeasonChips } from "@/components/teams/parts";
import { SeasonsChart } from "@/components/teams/seasons-chart";
import {
  MarginLine,
  OpponentsTable,
  PhaseTables,
  SeasonsTable,
  SplitsTable,
  SwingList,
  TopBatters,
  TopBowlers,
  TotalLine,
  VenuesTable,
} from "@/components/teams/team-sections";
import { ApiError, getTeam, type SeasonWindow as Window } from "@/lib/api/client";
import type { TeamProfile } from "@/lib/api/types";
import { getCompetition, isCompetitionId, type CompetitionId } from "@/lib/competitions";
import { parseSeason } from "@/lib/players";
import { parseTeamId, pct, recordText, seasonSpan } from "@/lib/teams";
import { CompetitionLink } from "@/components/competition/competition-link";

function windowFrom(raw: Record<string, string | string[] | undefined>): Window {
  const from = parseSeason(raw.from);
  const to = parseSeason(raw.to);
  return from && to && from > to ? { from: to, to: from } : { from, to };
}

async function load(
  competition: CompetitionId,
  rawId: string,
  window: Window,
): Promise<TeamProfile> {
  const id = parseTeamId(rawId);
  if (!id) notFound();
  try {
    return await getTeam(competition, id, window);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/teams/[id]">): Promise<Metadata> {
  const { competition, id } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  try {
    const { team } = await load(competition, id, {});
    const span = seasonSpan(team.first_season, team.last_season, competition);
    if (c.teamType === "national") {
      return {
        title: `${team.name}: ${c.label} record`,
        description: `${team.name} in ${c.collective}, ${span}: won ${pct(team.record.win_pct)} of decided matches. Year by year, against every opponent, by situation, by phase against par, players and comebacks.`,
      };
    }
    const titles = team.titles.length
      ? `${team.titles.length} ${team.titles.length === 1 ? "title" : "titles"} (${team.titles.join(", ")})`
      : "no titles yet";
    return {
      title: `${team.name}: ${c.label} record`,
      description: `${team.name} in the ${c.label}, ${span}: won ${pct(team.record.win_pct)} of decided matches, ${titles}. Season by season, by situation, by phase against par, players, rivals and comebacks.`,
    };
  } catch {
    return { title: "Team" };
  }
}

export default async function TeamPage({
  params,
  searchParams,
}: PageProps<"/[competition]/teams/[id]">) {
  const { id } = await params;
  const competition = (await params).competition as CompetitionId;
  const c = getCompetition(competition);
  const national = c.teamType === "national";
  const requested = windowFrom(await searchParams);
  const profile = await load(competition, id, requested);
  const { team, window } = profile;
  const career: [number, number] = [team.first_season, team.last_season];
  const whole = window.first === career[0] && window.last === career[1];
  const scope = whole ? "all seasons" : seasonSpan(window.first, window.last, competition);
  const linkWindow = {
    from: window.first === career[0] ? undefined : window.first,
    to: window.last === career[1] ? undefined : window.last,
  };
  const formerNames = team.names.filter((n) => n.name !== team.name);

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <CompetitionLink href="/teams" className="hover:text-foreground">
          Teams
        </CompetitionLink>
        <span aria-hidden="true"> / </span>
        <span className="text-foreground">{team.name}</span>
      </nav>

      <header className="flex flex-col gap-3">
        <span aria-hidden="true" className="flex gap-1">
          <span className="h-1.5 w-12 rounded-full" style={{ background: team.color }} />
          <span className="h-1.5 w-6 rounded-full" style={{ background: team.secondary_color }} />
        </span>
        <h1 className="text-3xl font-semibold tracking-tight">{team.name}</h1>
        <p className="text-sm text-muted-foreground">
          <span className="font-mono">{team.franchise_id}</span> ·{" "}
          {seasonSpan(team.first_season, team.last_season, competition)} · {team.seasons}{" "}
          {national
            ? team.seasons === 1
              ? "year"
              : "years"
            : team.seasons === 1
              ? "season"
              : "seasons"}
          {!team.is_active && !national && " · former franchise"}
          {formerNames.length > 0 &&
            ` · played as ${formerNames.map((n) => `${n.name} (${seasonSpan(n.first_season, n.last_season, competition)})`).join(", ")}`}
        </p>
      </header>

      <section aria-label="All-time record" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Matches" value={team.record.played}>
          {recordText(team.record)}
        </StatTile>
        <StatTile label="Won" value={pct(team.record.win_pct)}>
          of decided matches
        </StatTile>
        {national ? (
          <>
            <StatTile label="Years" value={team.seasons}>
              {seasonSpan(team.first_season, team.last_season, competition)}
            </StatTile>
            <StatTile label="Opponents" value={profile.opponents.length}>
              sides played in {scope}
            </StatTile>
          </>
        ) : (
          <>
            <StatTile label="Titles" value={team.titles.length}>
              <SeasonChips seasons={team.titles} empty="No title yet" />
            </StatTile>
            <StatTile label="Playoffs" value={team.playoffs.length}>
              {team.finals.length} {team.finals.length === 1 ? "final" : "finals"} in {team.seasons}{" "}
              seasons
            </StatTile>
          </>
        )}
      </section>

      <Panel
        id="seasons"
        title={national ? "Year by year" : "Season by season"}
        lede={
          national
            ? competition === "test"
              ? "Every Test in each calendar year: won, lost and drawn."
              : "Every match in each calendar year: won, lost and net run rate."
            : competition === "ipl"
              ? "League-stage record, points and net run rate exactly as in the official tables, and how far each season went."
              : `League-stage record, points (two a win) and net run rate computed from the results, and how far each season went.`
        }
      >
        <div className="flex flex-col gap-6">
          <SeasonsChart seasons={profile.seasons} />
          <SeasonsTable seasons={profile.seasons} national={national} />
        </div>
      </Panel>

      {team.seasons > 1 && (
        <SeasonWindow
          career={career}
          first={window.first}
          last={window.last}
          allLabel={national ? "All years" : "All seasons"}
        />
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          id="situations"
          title="Results by situation"
          lede={`${recordText(profile.record)} in ${scope} (${pct(profile.record.win_pct)}). ${national ? "A home game is one played in the side's own country." : "A home game is one at a ground the side used as its home that season."}`}
        >
          <SplitsTable groups={profile.splits} />
          <div className="mt-5 flex flex-col gap-2 rounded-xl bg-muted/40 p-4 text-sm">
            <p className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">Close finishes</span>
              <RecordCell record={profile.close} />
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Won by 5 runs or fewer, with 2 balls or fewer to spare, or in a super over. Records in
              close finishes do not carry over from one season to the next any more than chance
              would in the IPL; see{" "}
              <Link
                href="/ipl/lab/rivalries"
                className="text-primary underline-offset-4 hover:underline"
              >
                Do rivalries and close finishes repeat?
              </Link>
            </p>
          </div>
        </Panel>

        <Panel
          id="scoring"
          title="Totals and margins"
          lede={
            profile.scoring.avg_first_innings === null ||
            profile.scoring.avg_first_innings === undefined
              ? `In ${scope}.`
              : `Batting first, ${team.franchise_id} averaged ${profile.scoring.avg_first_innings.toFixed(1)} in ${profile.scoring.first_innings} full-length innings (${scope}).`
          }
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <TotalLine label="Highest total" total={profile.scoring.highest} />
            <TotalLine label="Lowest completed total" total={profile.scoring.lowest} />
            <MarginLine label="Biggest win by runs" margin={profile.scoring.biggest_win_runs} />
            <MarginLine
              label="Biggest win by wickets"
              margin={profile.scoring.biggest_win_wickets}
            />
          </div>
        </Panel>
      </div>

      <Panel
        id="phases"
        title="How they bat and bowl"
        lede={`Run rate and balls per wicket in each phase against par: what the average ${c.label} side managed in the same seasons and phases, weighted to this side's overs. Positive is better for the side in both tables.`}
      >
        {profile.phases.length ? (
          <PhaseTables phases={profile.phases} />
        ) : (
          <p className="text-sm text-muted-foreground">No balls in these seasons.</p>
        )}
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          id="comebacks"
          title="Greatest comebacks"
          lede="Wins from the lowest win probability. Each opens the replay at that ball."
        >
          <SwingList swings={profile.comebacks} kind="comeback" />
        </Panel>
        <Panel
          id="collapses"
          title="Costliest defeats"
          lede="Defeats from the highest win probability."
        >
          <SwingList swings={profile.collapses} kind="collapse" />
        </Panel>
      </div>

      <Panel
        id="players"
        title={`Leading players for ${team.franchise_id}`}
        lede={`Runs and wickets for ${national ? "this side" : "this franchise"} only, ${scope}.`}
      >
        <div className="grid gap-6 md:grid-cols-2">
          <TopBatters batters={profile.batters} />
          <TopBowlers bowlers={profile.bowlers} />
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel id="opponents" title="Against each opponent">
          <OpponentsTable
            team={team.franchise_id}
            opponents={profile.opponents}
            window={linkWindow}
          />
        </Panel>
        <Panel id="venues" title="Most-played grounds">
          <VenuesTable venues={profile.venues} />
        </Panel>
      </div>
    </div>
  );
}
