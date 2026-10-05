import type { Metadata } from "next";
import Link from "next/link";

import { SimulationChip } from "@/components/simulator/sim-results";
import { SimulatorApp } from "@/components/simulator/simulator-app";
import { getLatestXI, getTeams } from "@/lib/api/client";
import type { SimXI } from "@/lib/api/types";
import { parseTeamId } from "@/lib/teams";

export const metadata: Metadata = {
  title: "Match Simulator",
  description:
    "Play any two IPL XIs against each other 10,000 times, ball by ball, with the CricIQ ball-outcome model: the spread of scores, each player's likely contribution and the effect of every change. A model simulation, backtested.",
};

async function latest(team: string | undefined): Promise<SimXI | null> {
  if (!team) return null;
  try {
    return await getLatestXI(team);
  } catch {
    return null;
  }
}

export default async function SimulatorPage({ searchParams }: PageProps<"/simulator">) {
  const raw = await searchParams;
  const a = parseTeamId(raw.a) ?? "MI";
  const b = parseTeamId(raw.b) ?? "CSK";
  const [overview, xiA, xiB] = await Promise.all([
    getTeams(),
    latest(a),
    latest(b === a ? undefined : b),
  ]);
  const teams = overview.franchises.map((f) => ({
    id: f.franchise_id,
    name: f.name,
    active: f.is_active,
  }));

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">Match Simulator</h1>
          <SimulationChip />
        </div>
        <p className="max-w-3xl text-muted-foreground">
          Pick two XIs and play the match 10,000 times, ball by ball. Every ball comes from the{" "}
          <Link
            href="/models?tab=ball-outcome"
            className="text-primary underline-offset-4 hover:underline"
          >
            ball-outcome model
          </Link>
          , who bowls each over from how captains used each bowler, and each match draws its own
          pitch and conditions. Sides start from each team&apos;s latest XI, in today&apos;s scoring
          era; change anything.
        </p>
      </header>
      <SimulatorApp teams={teams} initialA={xiA} initialB={xiB} />
    </div>
  );
}
