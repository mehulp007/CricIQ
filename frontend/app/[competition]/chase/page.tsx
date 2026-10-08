import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ChaseCalculator } from "@/components/chase/chase-calculator";
import { CompetitionLink } from "@/components/competition/competition-link";
import { getChaseSides } from "@/lib/api/client";
import { isCompetitionId, isTest, type CompetitionId } from "@/lib/competitions";
import { formatDate } from "@/lib/format";
import { testModels } from "@/lib/models";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/chase">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition) || !isTest(competition)) return {};
  return {
    title: "Test Chase Calculator",
    description:
      "Set up a fourth-innings chase between any two Test sides: the target, the wickets in hand, the time left and where it is played. The CricIQ Test win probability model gives the chances of a win, a draw and a defeat.",
  };
}

function pick(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ChasePage({
  params,
  searchParams,
}: PageProps<"/[competition]/chase">) {
  const competition = (await params).competition as CompetitionId;
  if (!isTest(competition)) notFound();
  // `?batting=IND&fielding=AUS` opens the calculator on those sides.
  const raw = await searchParams;
  const sides = await getChaseSides(competition);
  const ids = sides.sides.map((s) => s.franchise_id);
  const batting = ids.find((id) => id === pick(raw.batting)?.toUpperCase()) ?? ids[0];
  const fielding =
    ids.find((id) => id === pick(raw.fielding)?.toUpperCase() && id !== batting) ??
    ids.find((id) => id !== batting) ??
    ids[1];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Chase Calculator</h1>
        <p className="max-w-3xl text-muted-foreground">
          A fourth-innings chase between any two Test sides. Set the target, the wickets in hand and
          the time left, and the{" "}
          <CompetitionLink
            href="/models"
            className="text-primary underline-offset-4 hover:underline"
          >
            Test win probability model
          </CompetitionLink>{" "}
          gives the chances of a win, a draw and a defeat. The sides&apos; strength is their rating
          from their Test results
          {sides.as_of ? ` up to ${formatDate(sides.as_of)}` : ""}, and the XIs are taken as level.
          Tests have no match simulator: a five-day match turns on declarations and time, which a
          ball-by-ball simulation cannot know.
        </p>
      </header>
      <ChaseCalculator
        competition={competition}
        sides={sides.sides}
        initialBatting={batting}
        initialFielding={fielding}
        usesRatings={(testModels().winProbability.groups["4"] ?? []).some((g) => g.key === "teams")}
      />
    </div>
  );
}
