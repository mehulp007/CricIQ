import type { Metadata } from "next";

import { BallOutcomeInsights } from "@/components/models/ball-outcome-insights";
import { FormatOverview } from "@/components/models/format-overview";
import { ModelsOverview } from "@/components/models/overview";
import { GroupOverview } from "@/components/models/group-overview";
import { RatingsInsights } from "@/components/models/ratings-insights";
import { ScoreProjectionInsights } from "@/components/models/score-projection-insights";
import { SimulatorInsights } from "@/components/models/simulator-insights";
import { WinProbabilityInsights } from "@/components/models/win-probability-insights";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getCompetition,
  isCompetitionId,
  phrase,
  possessive,
  type CompetitionId,
} from "@/lib/competitions";
import { modelsFor } from "@/lib/models";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/models">): Promise<Metadata> {
  const { competition } = await params;
  const label = isCompetitionId(competition) ? getCompetition(competition).label : "";
  return {
    title: `${label} Model Insights`,
    description:
      "How accurate CricIQ's models are and how each was built and tested: every model against its baseline on seasons it never saw, calibration, backtests, shrinkage, stability, rejected features and limitations.",
  };
}

const TABS = [
  "overview",
  "win-probability",
  "score-projection",
  "ball-outcome",
  "ratings",
  "simulator",
];

export default async function ModelInsightsPage({
  params,
  searchParams,
}: PageProps<"/[competition]/models">) {
  const competition = (await params).competition as CompetitionId;
  const models = modelsFor(competition);
  const c = getCompetition(competition);
  const tabs = models.simulator ? TABS : TABS.filter((t) => t !== "simulator");
  const raw = (await searchParams).tab;
  const requested = Array.isArray(raw) ? raw[0] : raw;
  const tab = requested && tabs.includes(requested) ? requested : "overview";
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {c.label} Model Insights
        </h1>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">
          {models.group === "odi"
            ? "ODIs have models of their own, trained on ODIs alone: each side's chance of winning after every ball, the projected 50-over total, the next ball's odds behind the Matchup Lab, CricIQ Ratings and the match simulator. The overview shows how each did on years it never saw, whichever way it came out; each tab shows how it was built and tested."
            : models.group === "t20i"
              ? "Men's T20 internationals have models of their own, trained on T20Is alone: each side's chance of winning after every ball, the projected first-innings total, the next ball's odds behind the Matchup Lab and CricIQ Ratings. The overview shows how each did on years it never saw, whichever way it came out; each tab shows how it was built and tested."
              : models.group === "leagues"
                ? `Win probability, projected totals, next-ball odds${models.simulator ? " and the simulator" : ""} for ${phrase(competition)} come from models trained on the BBL, CPL, PSL and SA20 only, with no IPL or international matches, and CricIQ Ratings are fitted on ${possessive(competition)} own records. The overview shows how each model did on ${possessive(competition)} own test matches; each tab shows how it was built and tested on the four leagues together.`
                : "Three models: each side's chance of winning after every ball, the projected total during the first innings, and the outcome of the next ball behind the Matchup Lab; plus CricIQ Ratings, which rate players with honest allowances for sample size, and the match simulator built on the ball model. The overview shows how accurate each one is on seasons it never saw; each tab shows how it was built and tested, and where it falls short."}
        </p>
      </header>

      <Tabs key={tab} defaultValue={tab}>
        <TabsList className="max-w-full flex-wrap justify-start group-data-horizontal/tabs:h-auto [&>[data-slot=tabs-trigger]]:h-7 [&>[data-slot=tabs-trigger]]:flex-none">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="win-probability">Win probability</TabsTrigger>
          <TabsTrigger value="score-projection">Score projection</TabsTrigger>
          <TabsTrigger value="ball-outcome">Ball outcome</TabsTrigger>
          <TabsTrigger value="ratings">Ratings</TabsTrigger>
          {models.simulator && <TabsTrigger value="simulator">Simulator</TabsTrigger>}
        </TabsList>
        <TabsContent value="overview" className="mt-6">
          {models.group === "odi" || models.group === "t20i" ? (
            <FormatOverview models={models} />
          ) : models.group === "leagues" ? (
            <GroupOverview models={models} />
          ) : (
            <ModelsOverview />
          )}
        </TabsContent>
        <TabsContent value="win-probability" className="mt-6">
          <WinProbabilityInsights
            data={models.winProbability}
            competition={competition}
            swings={models.swings}
          />
        </TabsContent>
        <TabsContent value="score-projection" className="mt-6">
          <ScoreProjectionInsights data={models.scoreProjection} />
        </TabsContent>
        <TabsContent value="ball-outcome" className="mt-6">
          <BallOutcomeInsights data={models.ballOutcome} competition={competition} />
        </TabsContent>
        <TabsContent value="ratings" className="mt-6">
          <RatingsInsights data={models.ratings} competition={competition} />
        </TabsContent>
        {models.simulator && (
          <TabsContent value="simulator" className="mt-6">
            <SimulatorInsights data={models.simulator} competition={competition} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
