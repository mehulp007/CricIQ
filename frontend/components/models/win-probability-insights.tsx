import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { BacktestChart, ReliabilityChart, SeriesLegend } from "@/components/models/charts";
import { Section, Stat, signed } from "@/components/models/section";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/format";
import {
  competitionPath,
  getCompetition,
  seasonLabel,
  type CompetitionId,
} from "@/lib/competitions";
import { type ModelInsights, SERIES, seasonSpan, type Swing, WIN_PROBABILITY } from "@/lib/models";
import { scrollRegion } from "@/lib/a11y";

const PHASES = { powerplay: "Powerplay", middle: "Middle overs", death: "Death overs" } as const;

export function WinProbabilityInsights({
  data: wp = WIN_PROBABILITY,
  competition = "ipl",
  swings = wp.swings,
}: {
  data?: ModelInsights;
  competition?: CompetitionId;
  swings?: Swing[];
}) {
  const { test } = wp;
  const label = getCompetition(competition).label;
  const testSeasons = seasonSpan(wp.splits.test);
  const wins = wp.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss).length;
  const served = Object.fromEntries(
    wp.feature_selection
      .filter((r) => r.variant === "served")
      .map((r) => [r.innings_no, r.log_loss]),
  );
  const candidates = wp.feature_selection.filter((r) => r.variant !== "served");
  const worst = Math.max(...candidates.map((r) => r.log_loss - served[r.innings_no]), 0.001);
  const calibration = wp.calibration.selection;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="font-mono text-[11px] text-primary">
            Win probability v{wp.version}
          </Badge>
          <Badge variant="outline" className="font-mono text-[11px] text-muted-foreground">
            Trained on {seasonSpan(wp.trained_on.seasons)} ·{" "}
            {wp.trained_on.matches.toLocaleString("en-IN")} matches
          </Badge>
        </div>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">
          Each side&apos;s chance of winning after every ball. Tested once on {test.matches} matches
          from {testSeasons} that the model never saw during training.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Log loss"
          value={test.model.log_loss.toFixed(3)}
          context={`vs ${test.baseline.log_loss.toFixed(3)} for a logistic-regression baseline. Lower is better.`}
        />
        <Stat
          label="Brier score"
          value={test.model.brier.toFixed(3)}
          context={`vs ${test.baseline.brier.toFixed(3)} for the baseline. Mean squared error of the probabilities.`}
        />
        <Stat
          label="Calibration error"
          value={`${(test.model.ece * 100).toFixed(1)}%`}
          context="Average gap between the predicted and actual win rate (ECE, 10 bins)."
        />
        <Stat
          label="Gain over baseline"
          value={signed(test.vs_baseline.improvement)}
          context={`Log loss, 95% interval ${signed(test.vs_baseline.ci_low)} to ${signed(test.vs_baseline.ci_high)}, resampling whole matches.`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="calibration-heading"
          title="Does 70% mean 70%?"
          lede={`Match states in ${testSeasons} grouped by predicted win probability, against how often the side actually won. Points on the dashed diagonal are perfectly calibrated.`}
        >
          <div className="mb-3 flex justify-end">
            <SeriesLegend />
          </div>
          <ReliabilityChart model={test.reliability} baseline={test.baseline_reliability} />
        </Section>

        <Section
          id="backtest-heading"
          title="Every season, not just the last two"
          lede={`For each season, the model is retrained on earlier seasons only and scored on that season. It beats the baseline in ${wins} of ${wp.backtest.length} seasons. A season is only 57–74 matches, so single seasons are noisy.`}
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-xs text-muted-foreground">Log loss (lower is better)</span>
            <SeriesLegend />
          </div>
          <BacktestChart rows={wp.backtest} />
        </Section>
      </div>

      <Section
        id="compare-heading"
        title="Against simpler models"
        lede="The same test matches, scored by the served model, the same model with other calibration choices, boosted trees that see only the score, and a logistic regression on the match state."
      >
        <div className="overflow-x-auto" {...scrollRegion("Model comparison")}>
          <table className="w-full min-w-lg text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Model</th>
                <th className="py-2 pr-3 text-right font-medium">Log loss</th>
                <th className="py-2 pr-3 text-right font-medium">Brier</th>
                <th className="py-2 pr-3 text-right font-medium">ECE</th>
                <th className="py-2 text-right font-medium">AUC</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {[
                { label: "CricIQ win probability (served)", m: test.model, strong: true },
                ...test.alternatives.map((a) => ({
                  label:
                    a.key === "platt"
                      ? "Same model, Platt-calibrated on the two latest seasons"
                      : a.key === "isotonic"
                        ? "Same model, isotonic calibration"
                        : "Same model, uncalibrated",
                  m: a,
                  strong: false,
                })),
                { label: "Boosted trees, match state only", m: test.state_only, strong: false },
                {
                  label: "Logistic regression on the match state",
                  m: test.baseline,
                  strong: false,
                },
              ].map(({ label, m, strong }) => (
                <tr key={label} className={strong ? "text-foreground" : "text-muted-foreground"}>
                  <th
                    scope="row"
                    className={`py-2.5 pr-3 text-left font-sans ${strong ? "font-medium" : "font-normal"}`}
                  >
                    {label}
                  </th>
                  <td className="py-2.5 pr-3 text-right">{m.log_loss.toFixed(3)}</td>
                  <td className="py-2.5 pr-3 text-right">{m.brier.toFixed(3)}</td>
                  <td className="py-2.5 pr-3 text-right">{m.ece.toFixed(3)}</td>
                  <td className="py-2.5 text-right">{m.auc?.toFixed(3) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          Over boosted trees that see only the score, the gain is{" "}
          {signed(test.vs_state_only.improvement)} log loss (95% interval{" "}
          {signed(test.vs_state_only.ci_low)} to {signed(test.vs_state_only.ci_high)}). That gain
          comes from the scoring-era adjustment and the chase dynamic programme.
        </p>
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="phase-heading"
          title="Where it helps most"
          lede="Log loss by innings and phase. The start of the first innings is close to a coin flip for every model: before a ball is bowled, nothing reliably separates the sides."
        >
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Phase</th>
                <th className="py-2 pr-3 text-right font-medium">Model</th>
                <th className="py-2 pr-3 text-right font-medium">Baseline</th>
                <th className="py-2 text-right font-medium">Balls</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {test.by_phase.map((r) => (
                <tr key={`${r.innings_no}-${r.phase}`}>
                  <th scope="row" className="py-2.5 pr-3 text-left font-normal">
                    <span className="text-muted-foreground">
                      {r.innings_no === 1 ? "1st inns" : "Chase"} ·{" "}
                    </span>
                    {PHASES[r.phase]}
                  </th>
                  <td className="py-2.5 pr-3 text-right font-mono tabular-nums">
                    {r.model_log_loss.toFixed(3)}
                  </td>
                  <td className="py-2.5 pr-3 text-right font-mono text-muted-foreground tabular-nums">
                    {r.baseline_log_loss.toFixed(3)}
                  </td>
                  <td className="py-2.5 text-right font-mono text-muted-foreground tabular-nums">
                    {r.rows.toLocaleString("en-IN")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section
          id="explain-heading"
          title="What drives an estimate"
          lede="Each estimate is explained with TreeSHAP, computed exactly by LightGBM, and grouped into three cricket concepts. This is each concept's share of the explanations on the test matches."
        >
          <ul className="flex flex-col gap-4">
            {wp.importance.map((item) => (
              <li key={item.group} className="flex flex-col gap-1.5">
                <div className="flex justify-between text-sm">
                  <span>{item.label}</span>
                  <span className="font-mono tabular-nums">{Math.round(item.share * 100)}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted" aria-hidden="true">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${item.share * 100}%`, background: SERIES.model.color }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <Section
        id="selection-heading"
        title="What didn't make the cut"
        lede={`Player, venue and squad strength were each built leak-free: they use only matches played earlier, shrunk toward the league average. Each one the model does not already use was then added to it and scored season by season on ${seasonSpan(candidates[0]?.seasons ?? [])}, before the test seasons. ${candidates.some((r) => r.log_loss < served[r.innings_no]) ? "Those that beat the served model are below with a negative change." : "None beat the served model, so none was added."} Once a match is under way, the score, wickets and balls left carry most of the signal.`}
      >
        <ul className="flex flex-col gap-3">
          {candidates.map((r) => {
            const delta = r.log_loss - served[r.innings_no];
            return (
              <li
                key={`${r.innings_no}-${r.variant}`}
                className="grid gap-1.5 sm:grid-cols-[1fr_14rem] sm:items-center sm:gap-4"
              >
                <span className="text-sm">
                  <span className="text-muted-foreground">
                    {r.innings_no === 1 ? "1st inns" : "Chase"} ·{" "}
                  </span>
                  {r.label.replace(/^\+ /, "")}
                </span>
                <span className="flex items-center gap-3">
                  <span className="h-2 flex-1 rounded-full bg-muted" aria-hidden="true">
                    <span
                      className="block h-full rounded-full"
                      style={{
                        width: `${(Math.max(delta, 0) / worst) * 100}%`,
                        background: SERIES.baseline.color,
                      }}
                    />
                  </span>
                  <span className="w-16 text-right font-mono text-xs tabular-nums">
                    {signed(delta)}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
        <p className="mt-4 text-xs text-muted-foreground">
          Change in log loss when the group is added (positive = worse).
        </p>
      </Section>

      <Section
        id="calibration-choice-heading"
        title="Calibration, decided by the data"
        lede="Calibrating on the latest seasons tracks the rising scoring rate, but it costs those seasons as training data, and a season-specific shift (dew, the toss) can overshoot. So each training run measures both options on the seasons before the test set and keeps the better one."
      >
        <ul className="grid gap-3 sm:grid-cols-2">
          {calibration.map((c) => (
            <li
              key={c.method}
              className={`rounded-xl border p-4 ${c.method === wp.calibration.method ? "border-primary/60" : "border-border"}`}
            >
              <p className="text-sm font-medium">
                {c.method === "none"
                  ? "Train on every earlier season"
                  : "Hold out two seasons to calibrate"}
                {c.method === wp.calibration.method && (
                  <Badge variant="outline" className="ml-2 text-[10px] text-primary">
                    Chosen
                  </Badge>
                )}
              </p>
              <p className="mt-1 font-mono text-xs text-muted-foreground tabular-nums">
                Log loss {c.log_loss.toFixed(4)} · Brier {c.brier.toFixed(4)}
              </p>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        id="swings-heading"
        title={`The biggest swings in ${label} history`}
        lede={`The single biggest win-probability swing from each match, across every ${label} season. Open one to replay the moment.`}
      >
        <ol className="flex flex-col divide-y divide-border">
          {swings.map((s) => (
            <li key={`${s.match_id}`}>
              <Link
                href={competitionPath(
                  competition,
                  `/matches/${s.match_id}?ball=${s.innings_no}.${s.seq_no}`,
                )}
                className="group flex flex-wrap items-baseline gap-x-4 gap-y-1 py-3 text-sm"
              >
                <span className="w-20 shrink-0 font-mono text-xs text-muted-foreground tabular-nums">
                  +{s.swing.toFixed(0)} pts
                </span>
                <span className="min-w-0 flex-1">
                  <span className="font-medium group-hover:text-primary">{s.description}</span>
                  <span className="block text-xs text-muted-foreground">
                    {s.teams}, {seasonLabel(competition, s.season)} · ball {s.ball_label} ·{" "}
                    {s.result}
                  </span>
                </span>
                <span className="flex items-center gap-1 text-xs text-muted-foreground group-hover:text-primary">
                  {formatDate(s.date)}
                  <ArrowUpRight className="size-3.5" aria-hidden="true" />
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </Section>

      <Section
        id="method-heading"
        title="How it works"
        lede="Two gradient-boosted tree models (LightGBM): one for the first innings, one for the chase."
      >
        <ul className="grid gap-4 text-sm leading-relaxed text-muted-foreground md:grid-cols-2">
          <li>
            <span className="font-medium text-foreground">Leak-free by construction.</span> Every
            feature uses only what was known at that ball, or earlier matches. A test deletes and
            rewrites all later matches and checks that no earlier feature changes.
          </li>
          <li>
            <span className="font-medium text-foreground">Cricket common sense built in.</span>{" "}
            Monotonic constraints mean more runs, fewer wickets lost, fewer runs needed or more
            balls left can never lower the batting side&apos;s chance.
          </li>
          <li>
            <span className="font-medium text-foreground">Scores in context.</span> A rolling league
            scoring rate keeps a 180 in 2010 comparable with a 180 in 2025, when totals were far
            higher.
          </li>
          <li>
            <span className="font-medium text-foreground">Sharp at the finish.</span> A WASP-style
            dynamic programme computes the exact chance of a chase from runs needed, balls and
            wickets. It knows that 13 off the last ball is impossible, where data alone is thin.
          </li>
          <li>
            <span className="font-medium text-foreground">Tuned without touching the test.</span>{" "}
            Hyperparameters are tuned on {seasonSpan(wp.splits.validation)}. Calibration and feature
            choices use the seasons before {Math.min(...wp.splits.test)}.
          </li>
          <li>
            <span className="font-medium text-foreground">Limits.</span> About 1,200 matches is a
            small sample. Weather, pitch reports and team news are not in the data, and super overs
            are not modelled. These are estimates of historical patterns, not predictions or betting
            advice.
          </li>
        </ul>
      </Section>
    </div>
  );
}
