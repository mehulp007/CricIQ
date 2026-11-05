import type { Metadata } from "next";

import { Panel } from "@/components/players/profile-parts";
import { GroundsTable } from "@/components/phases/grounds-table";
import { OverChart } from "@/components/phases/over-chart";
import { PhaseCards } from "@/components/phases/phase-cards";
import { PhaseLeadersTabs } from "@/components/phases/phase-leaders";
import { ResultsPanel } from "@/components/phases/results-panel";
import { CoverageNote } from "@/components/ui/coverage-note";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar, type FilterField } from "@/components/ui/filter-bar";
import { PageHeader } from "@/components/ui/page-header";
import { getMeta, getPhases } from "@/lib/api/client";
import {
  getCompetition,
  isCompetitionId,
  isTest,
  seasonLabel,
  type CompetitionId,
} from "@/lib/competitions";
import { inningsChoices, MIN_BALL_CHOICES, phaseQuery } from "@/lib/phases";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/phases">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.label} phases`,
    description: isTest(competition)
      ? "How Test innings are built: the new ball, the middle overs and the second new ball, ten overs at a time, with the leading batters and bowlers in each."
      : `How ${c.label} innings are built: run rate, wickets, boundaries and dots in the powerplay, middle and death overs, over by over, with the leaders in each phase.`,
  };
}

export default async function PhasesPage({
  params,
  searchParams,
}: PageProps<"/[competition]/phases">) {
  const competition = (await params).competition as CompetitionId;
  const c = getCompetition(competition);
  const test = isTest(competition);
  const query = phaseQuery(await searchParams, c.format);
  const [data, meta] = await Promise.all([getPhases(competition, query), getMeta(competition)]);

  const seasons = meta.seasons
    .filter((s) => s.matches > 0)
    .map((s) => ({
      value: String(s.year),
      label: s.label,
    }));
  const teamWord = c.teamType === "national" ? "side" : "team";
  const fields: FilterField[] = [
    { param: "from", label: "From season", all: "First season", choices: seasons, width: "w-36" },
    { param: "to", label: "To season", all: "Latest season", choices: seasons, width: "w-36" },
    {
      param: "team",
      label: c.teamType === "national" ? "Side" : "Team",
      all: `All ${teamWord}s`,
      choices: meta.franchises.map((f) => ({ value: f.franchise_id, label: f.name })),
      width: "w-52",
    },
    {
      param: "venue",
      label: "Ground",
      all: "All grounds",
      choices: [...meta.venues]
        .sort((a, b) => b.matches - a.matches)
        .map((v) => ({ value: v.venue_id, label: `${v.name} (${v.matches})` })),
      width: "w-60",
    },
    {
      param: "innings",
      label: "Innings",
      all: test ? "Every innings" : "Both innings",
      choices: inningsChoices(c.format),
      width: "w-40",
    },
    {
      param: "min_balls",
      label: "Leaders' minimum balls",
      all: `Min ${data.filters.min_balls} balls`,
      choices: MIN_BALL_CHOICES.map((n) => ({ value: String(n), label: `Min ${n} balls` })),
      width: "w-40",
    },
  ];

  const team = data.filters.team
    ? (meta.franchises.find((f) => f.franchise_id === data.filters.team)?.name ?? data.filters.team)
    : null;
  const empty = data.phases.every((p) => p.innings === 0);
  const span =
    data.coverage.first_season && data.coverage.last_season
      ? `${seasonLabel(competition, data.coverage.first_season)}–${seasonLabel(competition, data.coverage.last_season)}`
      : "";
  const footer = `Data: Cricsheet (ODC-BY 1.0) · ${c.label} ${span} · data ${meta.data_version}`;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="How innings are built"
        title="Phases"
        description={
          test
            ? "Run rate, wickets, boundaries and dots with the new ball, through the middle overs and after the second new ball, ten overs at a time, with the leading batters and bowlers in each."
            : `Run rate, wickets, boundaries and dots in the powerplay, the middle overs and at the death, over by over, with who wins batting first and the leading batters and bowlers in each phase.`
        }
      />
      <div className="flex flex-col gap-3">
        <FilterBar fields={fields} />
        <CoverageNote competition={c.label} coverage={data.coverage} />
      </div>

      {empty ? (
        <EmptyState
          title="No innings match these filters"
          description="Try a wider season range, another ground or both innings."
        />
      ) : (
        <>
          <section aria-labelledby="by-phase" className="flex flex-col gap-4">
            <h2 id="by-phase" className="text-lg font-semibold tracking-tight">
              {team ? `${team}: batting phase by phase` : "Phase by phase"}
            </h2>
            <PhaseCards phases={data.phases} />
          </section>

          <Panel
            id="over-by-over"
            title="Over by over"
            lede={
              test
                ? "The run rate in each block of ten overs across the innings that reached it, coloured by phase, with wickets per over as the line."
                : "The run rate in each over across the innings that reached it, coloured by phase, with wickets per over as the line."
            }
          >
            <OverChart
              overs={data.overs}
              phases={data.phases}
              block={data.over_block}
              competition={team ? `${c.label}, ${team}` : c.label}
              footer={footer}
            />
          </Panel>

          <Panel
            id="results"
            title={test ? "Batting first or second" : "Batting first or chasing"}
            lede="Matches with a result (a tie settled by a super over counts for its winner); no results are left out. Season and ground filters apply; the innings filter doesn't."
          >
            <ResultsPanel results={data.results} toss={data.toss} test={test} team={team} />
          </Panel>

          <Panel
            id="leaders"
            title="Phase leaders"
            lede={`The most runs and wickets in each phase, among players with at least ${data.filters.min_balls} balls in it. Equal figures share a rank.`}
          >
            <PhaseLeadersTabs
              leaders={data.leaders}
              phases={data.phases}
              minBalls={data.filters.min_balls}
            />
          </Panel>

          {data.grounds.length > 0 && (
            <Panel
              id="grounds"
              title="Grounds by phase"
              lede="Run rate in each phase at the busiest grounds, from the balls bowled there. CricIQ has no pitch or weather data."
            >
              <GroundsTable grounds={data.grounds} phases={data.phases} />
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
