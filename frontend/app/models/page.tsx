import type { Metadata } from "next";

import { BallOutcomeInsights } from "@/components/models/ball-outcome-insights";
import { RatingsInsights } from "@/components/models/ratings-insights";
import { ScoreProjectionInsights } from "@/components/models/score-projection-insights";
import { SimulatorInsights } from "@/components/models/simulator-insights";
import { WinProbabilityInsights } from "@/components/models/win-probability-insights";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const metadata: Metadata = {
  title: "Model Insights",
  description:
    "How CricIQ's win probability, score projection and ball-outcome models, CricIQ Ratings and the match simulator were built and tested: calibration, season-by-season backtests, shrinkage, stability, rejected features and limitations.",
};

const TABS = ["win-probability", "score-projection", "ball-outcome", "ratings", "simulator"];

export default async function ModelInsightsPage({ searchParams }: PageProps<"/models">) {
  const raw = (await searchParams).tab;
  const requested = Array.isArray(raw) ? raw[0] : raw;
  const tab = requested && TABS.includes(requested) ? requested : "win-probability";
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Model Insights</h1>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">
          Three models: each side&apos;s chance of winning after every ball, the projected total
          during the first innings, and the outcome of the next ball behind the Matchup Lab; plus
          CricIQ Ratings, which rate players with honest allowances for sample size, and the match
          simulator built on the ball model. This page shows how each was built and tested, and
          where it falls short.
        </p>
      </header>

      <Tabs defaultValue={tab}>
        <TabsList>
          <TabsTrigger value="win-probability">Win probability</TabsTrigger>
          <TabsTrigger value="score-projection">Score projection</TabsTrigger>
          <TabsTrigger value="ball-outcome">Ball outcome</TabsTrigger>
          <TabsTrigger value="ratings">Ratings</TabsTrigger>
          <TabsTrigger value="simulator">Simulator</TabsTrigger>
        </TabsList>
        <TabsContent value="win-probability" className="mt-6">
          <WinProbabilityInsights />
        </TabsContent>
        <TabsContent value="score-projection" className="mt-6">
          <ScoreProjectionInsights />
        </TabsContent>
        <TabsContent value="ball-outcome" className="mt-6">
          <BallOutcomeInsights />
        </TabsContent>
        <TabsContent value="ratings" className="mt-6">
          <RatingsInsights />
        </TabsContent>
        <TabsContent value="simulator" className="mt-6">
          <SimulatorInsights />
        </TabsContent>
      </Tabs>
    </div>
  );
}
