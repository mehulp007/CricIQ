import Link from "next/link";

import { BallBacktestChart, SeriesLegend } from "@/components/models/charts";
import { OutcomeCalibrationPicker } from "@/components/models/outcome-calibration";
import { Section, Stat } from "@/components/models/section";
import { Badge } from "@/components/ui/badge";
import { competitionPath, type CompetitionId } from "@/lib/competitions";
import { BALL_OUTCOME, type BallOutcomeInsights as Insights, seasonSpan } from "@/lib/models";
import { scrollRegion } from "@/lib/a11y";

const PHASES: Record<string, string> = {
  powerplay: "Powerplay",
  middle: "Middle overs",
  death: "Death overs",
  new_ball: "New ball",
  second_new_ball: "Second new ball",
};
const HISTORY: Record<string, string> = {
  "1-9": "1–9 balls",
  "10-29": "10–29 balls",
  "30+": "30 balls or more",
};

function gain(model: number, other: number): string {
  return `${(((other - model) / other) * 100).toFixed(2)}%`;
}

export function BallOutcomeInsights({
  data: bo = BALL_OUTCOME,
  competition = "ipl",
}: {
  data?: Insights;
  competition?: CompetitionId;
}) {
  const { test, matchups } = bo;
  const testSeasons = seasonSpan(bo.splits.test);
  const wins = bo.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss).length;
  const rows = [
    ...matchups.by_history.map((r) => ({ label: HISTORY[r.history] ?? r.history, ...r })),
    { label: "All pairs who had met", ...matchups.all },
  ];

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="font-mono text-[11px] text-primary">
            Ball outcome v{bo.version}
          </Badge>
          <Badge variant="outline" className="font-mono text-[11px] text-muted-foreground">
            Trained on {seasonSpan(bo.trained_on.seasons)} ·{" "}
            {bo.trained_on.balls.toLocaleString("en-IN")} balls
          </Badge>
        </div>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">
          The chance of a dot, 1, 2, 3, 4, 6 or wicket on the next ball a batter faces. It powers
          the next-ball odds in the{" "}
          <Link
            href={competitionPath(competition, "/matchups")}
            className="text-foreground underline-offset-4 hover:underline"
          >
            Matchup Lab
          </Link>{" "}
          and is the baseline batter-vs-bowler records are shrunk towards. Tested once on{" "}
          {test.model.balls.toLocaleString("en-IN")} balls from {testSeasons}.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Better than baseline"
          value={gain(test.model.log_loss, test.baseline.log_loss)}
          context="Lower log loss than outcome frequencies by phase and wickets from the two previous seasons."
        />
        <Stat
          label="What players add"
          value={gain(test.model.log_loss, test.situation_only.log_loss)}
          context="On top of the match situation alone. Single balls are noisy, so gains are small for any model."
        />
        <Stat
          label="Head-to-head prior"
          value={`${Math.round(bo.kappa)} balls`}
          context="How much evidence the players' overall records are worth against a pair's own history."
        />
        <Stat
          label="Runs per ball"
          value={test.model.expected_runs.toFixed(3)}
          context={`Predicted on the test seasons, against ${test.model.actual_runs.toFixed(3)} actually scored.`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="outcome-calibration-heading"
          title="Does a 10% six mean 10%?"
          lede={`Each outcome's predicted probability against how often it happened in ${testSeasons}. Points on the dashed diagonal are exactly calibrated.`}
        >
          <OutcomeCalibrationPicker outcomes={bo.outcomes} calibration={test.calibration} />
        </Section>

        <Section
          id="ball-backtest-heading"
          title="Every season, not just the last two"
          lede={`Fit on every earlier season, then scored season by season. Lower log loss than the baseline in ${wins} of ${bo.backtest.length} seasons.`}
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-xs text-muted-foreground">Log loss (lower is better)</span>
            <SeriesLegend baseline="Phase and wickets" />
          </div>
          <BallBacktestChart rows={bo.backtest} />
        </Section>
      </div>

      <Section
        id="history-heading"
        title="Do head-to-head records predict the future?"
        lede={`For pairs who had met before ${bo.splits.test[0]}, three ways to predict their ${testSeasons} balls: the model alone, the model adjusted by the shrunk head-to-head record, and the raw head-to-head rates. Log loss, lower is better.`}
      >
        <div className="overflow-x-auto" {...scrollRegion("Head-to-head check")}>
          <table className="w-full min-w-xl text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">History before the test</th>
                <th className="py-2 pr-3 text-right font-medium">Balls</th>
                <th className="py-2 pr-3 text-right font-medium">Model alone</th>
                <th className="py-2 pr-3 text-right font-medium">Shrunk head-to-head</th>
                <th className="py-2 text-right font-medium">Raw head-to-head</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {rows.map((r) => (
                <tr key={r.label}>
                  <th scope="row" className="py-2.5 pr-3 text-left font-sans font-normal">
                    {r.label}
                  </th>
                  <td className="py-2.5 pr-3 text-right text-muted-foreground">
                    {r.balls.toLocaleString("en-IN")}
                  </td>
                  <td className="py-2.5 pr-3 text-right">{r.model.toFixed(4)}</td>
                  <td className="py-2.5 pr-3 text-right font-semibold">{r.shrunk.toFixed(4)}</td>
                  <td className="py-2.5 text-right text-muted-foreground">{r.raw.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Raw head-to-head rates are far worse than the model at predicting the same pair&apos;s
          next balls: a few dozen balls of history are mostly noise. Shrinking them by a prior worth{" "}
          {Math.round(matchups.kappa)} balls (fitted on earlier seasons) keeps the model&apos;s
          accuracy, which is why the Matchup Lab leads with the shrunk estimate.
        </p>
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="ball-phase-heading"
          title="By phase"
          lede="Log loss on the test seasons. The model gains most where who is batting and bowling matters most."
        >
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Phase</th>
                <th className="py-2 pr-3 text-right font-medium">Balls</th>
                <th className="py-2 pr-3 text-right font-medium">Model</th>
                <th className="py-2 text-right font-medium">Baseline</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {test.by_phase.map((r) => (
                <tr key={r.phase}>
                  <th scope="row" className="py-2.5 pr-3 text-left font-sans font-normal">
                    {PHASES[r.phase]}
                  </th>
                  <td className="py-2.5 pr-3 text-right text-muted-foreground">
                    {r.balls.toLocaleString("en-IN")}
                  </td>
                  <td className="py-2.5 pr-3 text-right">{r.model_log_loss.toFixed(4)}</td>
                  <td className="py-2.5 text-right text-muted-foreground">
                    {r.baseline_log_loss.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section
          id="ball-selection-heading"
          title="What went in, and what didn't"
          lede={`Compared on ${seasonSpan(bo.splits.tune_valid)} before the test seasons. A candidate joins only if it cuts log loss by at least ${(bo.candidate_min_gain * 100).toFixed(1)}%.`}
        >
          <ul className="flex flex-col divide-y divide-border text-sm">
            {bo.feature_selection.map((r) => (
              <li key={r.variant} className="flex items-baseline justify-between gap-3 py-2.5">
                <span>{r.label}</span>
                <span className="font-mono tabular-nums">{r.log_loss.toFixed(5)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Separate player effects per phase help a little, but by less than the bar, so the
            simpler model is served.
          </p>
        </Section>
      </div>

      <Section
        id="ball-method-heading"
        title="How it works"
        lede="Multinomial logistic regression with penalised player effects, plus empirical-Bayes shrinkage for head-to-head records."
      >
        <ul className="grid gap-4 text-sm leading-relaxed text-muted-foreground md:grid-cols-2">
          <li>
            <span className="font-medium text-foreground">The situation.</span> Phase and innings,
            wickets down, how many balls the batter has faced, batter hand against bowler type, the
            required rate in a chase, and the scoring era.
          </li>
          <li>
            <span className="font-medium text-foreground">The players.</span> Every batter and
            bowler gets an effect on each outcome, held close to average by a penalty tuned on
            held-out seasons. A newcomer starts at average and earns an effect ball by ball.
          </li>
          <li>
            <span className="font-medium text-foreground">Head-to-head.</span> A pair&apos;s record
            is blended with what the model expects for the same balls, weighted by balls ÷ (balls +{" "}
            {Math.round(bo.kappa)}). The prior strength is fitted across all pairs, not chosen by
            hand.
          </li>
          <li>
            <span className="font-medium text-foreground">Limits.</span> No ball tracking (line,
            length, pace or field), no venue or pitch effects, and player effects span a whole
            career, so in-season form moves them slowly.
          </li>
        </ul>
      </Section>
    </div>
  );
}
