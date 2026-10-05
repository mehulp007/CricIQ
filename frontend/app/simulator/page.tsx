import type { Metadata } from "next";
import Link from "next/link";

import { SimulationChip } from "@/components/simulator/sim-results";
import { SimulatorApp } from "@/components/simulator/simulator-app";
import { getSimSeasons, getSquad } from "@/lib/api/client";
import type { SimSquad } from "@/lib/api/types";
import { defaultTeams, pickSeason } from "@/lib/simulator";

export const metadata: Metadata = {
  title: "Match Simulator",
  description:
    "Pick any IPL season, two sides and their XIs from that season's squads, and play the match 10,000 times, ball by ball, with the CricIQ ball-outcome model: the spread of scores, each player's likely contribution and the effect of every change. A model simulation, backtested.",
};

async function squadOrNull(season: number, team: string | null): Promise<SimSquad | null> {
  if (!team) return null;
  try {
    return await getSquad(season, team);
  } catch {
    return null;
  }
}

export default async function SimulatorPage({ searchParams }: PageProps<"/simulator">) {
  const raw = await searchParams;
  const seasons = await getSimSeasons();
  const season = pickSeason(seasons, raw.season);
  const [a, b] = season ? defaultTeams(season, raw.a, raw.b) : [null, null];
  const [squadA, squadB] = season
    ? await Promise.all([squadOrNull(season.season, a), squadOrNull(season.season, b)])
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
          <Link
            href="/models?tab=ball-outcome"
            className="text-primary underline-offset-4 hover:underline"
          >
            ball-outcome model
          </Link>
          , who bowls each over from how captains used each bowler, and each match draws its own
          pitch and conditions. Scoring is as it was in the season you pick.
        </p>
      </header>
      <SimulatorApp
        seasons={seasons}
        initialSeason={season?.season ?? null}
        initialA={squadA}
        initialB={squadB}
      />
    </div>
  );
}
