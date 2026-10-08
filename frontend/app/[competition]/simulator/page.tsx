import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { CompetitionLink } from "@/components/competition/competition-link";
import { type PickRecord, SimulationChip } from "@/components/simulator/sim-results";
import { SimulatorApp } from "@/components/simulator/simulator-app";
import { getSimSeasons, getSquad } from "@/lib/api/client";
import type { SimSquad } from "@/lib/api/types";
import {
  competitionPath,
  getCompetition,
  isCompetitionId,
  isTest,
  type CompetitionId,
  type LimitedOversId,
} from "@/lib/competitions";
import { modelsFor, seasonSpan } from "@/lib/models";
import { defaultTeams, pickSeason } from "@/lib/simulator";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/simulator">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const label = getCompetition(competition).label;
  return {
    title: `${label} Match Simulator`,
    description: `Pick any ${label} season, two sides and their XIs from that season's squads, and play the match 10,000 times, ball by ball, with the CricIQ ball-outcome model: the spread of scores, each player's likely contribution and the effect of every change. A model simulation, backtested.`,
  };
}

async function squadOrNull(
  competition: CompetitionId,
  season: number,
  team: string | null,
): Promise<SimSquad | null> {
  if (!team) return null;
  try {
    return await getSquad(competition, season, team);
  } catch {
    return null;
  }
}

/** How the serving simulator's backtest picked winners, for the result's caption. */
function pickRecord(competition: LimitedOversId): PickRecord | null {
  const win = modelsFor(competition).simulator?.win;
  const backtest = modelsFor(competition).simulator;
  if (!win || !backtest) return null;
  const gain = win.gain_vs_coin_flip;
  return {
    verdict: gain.low > 0 ? "better" : gain.high < 0 ? "worse" : "coin",
    brier: win.simulator.brier,
    coinFlip: win.coin_flip.brier,
    seasons: seasonSpan(backtest.test),
  };
}

/** Where no simulator version has passed its backtest gate, the page says so. */
function NotServed({ competition }: { competition: LimitedOversId }) {
  const c = getCompetition(competition);
  const backtest = modelsFor(competition).simulatorBacktest;
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-6">
      <h2 className="text-lg font-semibold tracking-tight">No {c.label} simulator yet</h2>
      <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
        {backtest
          ? `A ${c.label} simulator was built and backtested on its ${seasonSpan(backtest.test)} seasons, and it failed its gate: its first-innings totals averaged ${backtest.first_innings.simulated_mean} against ${backtest.first_innings.actual_mean} actual, so the ${backtest.gate.join("; ")}. The ball model scores recent seasons a little low here. CricIQ only serves a simulator that passes, so there is none here until one does.`
          : `The simulator is backtested on each competition before it serves it, and it has not been backtested on the ${c.label} yet.`}
      </p>
      <p className="text-sm text-muted-foreground">
        Meanwhile, every {c.label} match can be replayed ball by ball with its{" "}
        <CompetitionLink
          href="/models?tab=win-probability"
          className="text-primary underline-offset-4 hover:underline"
        >
          win probability
        </CompetitionLink>
        , and the{" "}
        <Link
          href={competitionPath("ipl", "/simulator")}
          className="text-primary underline-offset-4 hover:underline"
        >
          IPL simulator
        </Link>{" "}
        plays any IPL match 10,000 times.
      </p>
    </div>
  );
}

export default async function SimulatorPage({
  params,
  searchParams,
}: PageProps<"/[competition]/simulator">) {
  const competition = (await params).competition as CompetitionId;
  // Tests have no match simulator: their chase calculator takes its place.
  if (isTest(competition)) redirect(competitionPath(competition, "/chase"));
  const c = getCompetition(competition);
  if (modelsFor(competition).simulator === null) {
    return (
      <div className="flex flex-col gap-6">
        <header className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold tracking-tight">{c.label} Match Simulator</h1>
        </header>
        <NotServed competition={competition} />
      </div>
    );
  }
  const raw = await searchParams;
  const seasons = await getSimSeasons(competition);
  const season = pickSeason(seasons, raw.season);
  const [a, b] = season ? defaultTeams(season, raw.a, raw.b) : [null, null];
  const [squadA, squadB] = season
    ? await Promise.all([
        squadOrNull(competition, season.season, a),
        squadOrNull(competition, season.season, b),
      ])
    : [null, null];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">Match Simulator</h1>
          <SimulationChip />
        </div>
        <p className="max-w-3xl text-muted-foreground">
          Pick a season and two sides, choose each XI from that season&apos;s squad, and play the
          match 10,000 times, ball by ball. Every ball comes from the{" "}
          <CompetitionLink
            href="/models?tab=ball-outcome"
            className="text-primary underline-offset-4 hover:underline"
          >
            ball-outcome model
          </CompetitionLink>
          , who bowls each over from how captains used each bowler, and each match draws its own
          pitch and conditions. Scoring is as it was in the season you pick.
        </p>
      </header>
      <SimulatorApp
        seasons={seasons}
        initialSeason={season?.season ?? null}
        initialA={squadA}
        initialB={squadB}
        picks={pickRecord(competition)}
      />
    </div>
  );
}
