import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Section, Stat } from "@/components/models/section";
import { scrollRegion } from "@/lib/a11y";
import { CLUTCH, MOMENTUM, PRESSURE, RIVALRIES } from "@/lib/lab";
import {
  BALL_OUTCOME,
  FIRST_SEASON,
  type ModelSplit,
  RATINGS,
  SCORE_PROJECTION,
  SIMULATOR,
  type SplitRole,
  WIN_PROBABILITY,
  favouriteAccuracy,
  modelSplits,
  roleIn,
  seasonSpan,
} from "@/lib/models";
import { cn } from "@/lib/utils";

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

const wp = WIN_PROBABILITY.test;
const sp = SCORE_PROJECTION.test;
const bo = BALL_OUTCOME.test;
const sim = SIMULATOR;
const accuracy = favouriteAccuracy(wp.reliability);
const baselineAccuracy = favouriteAccuracy(wp.baseline_reliability);
const ballGain = 1 - bo.model.log_loss / bo.baseline.log_loss;
const ballSeasons = BALL_OUTCOME.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss);
const projectionSeasons = SCORE_PROJECTION.backtest.filter((r) => r.mae < r.par_mae);
const wpSeasons = WIN_PROBABILITY.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss);
const ratingWins = RATINGS.components.filter(
  (c) => c.next_season.mse && c.next_season.mse.shrunk < c.next_season.mse.raw,
);
const death = sp.by_phase.find((r) => r.phase === "death");
const testSeasons = seasonSpan(WIN_PROBABILITY.splits.test);

interface Row {
  key: string;
  model: string;
  predicts: string;
  result: string;
  baseline: string;
  plain: string;
}

const ROWS: Row[] = [
  {
    key: "win-probability",
    model: "Win probability",
    predicts: "Each side's chance of winning after every ball",
    result: `Log loss ${wp.model.log_loss.toFixed(3)} · AUC ${(wp.model.auc ?? 0).toFixed(2)}`,
    baseline: `${wp.baseline.log_loss.toFixed(3)} · ${(wp.baseline.auc ?? 0).toFixed(2)} (logistic regression on the match state)`,
    plain: `The side it favours goes on to win after ${pct(accuracy)} of balls (baseline ${pct(baselineAccuracy)}), and its chances are off by ${(100 * wp.model.ece).toFixed(1)} points on average. Better than the baseline in ${wpSeasons.length} of ${WIN_PROBABILITY.backtest.length} backtest seasons.`,
  },
  {
    key: "score-projection",
    model: "Score projection",
    predicts: "The first-innings total, with an 80% range, after every ball",
    result: `Median error ${sp.model.mae.toFixed(1)} runs · 80% range holds ${pct(sp.model.coverage80)}`,
    baseline: `${sp.par_baseline.mae.toFixed(1)} runs · ${pct(sp.par_baseline.coverage80)} (par for the era); run rate ${sp.run_rate.mae.toFixed(1)} runs`,
    plain: `A typical projection misses by about ${Math.round(sp.model.mae)} runs (${death ? `${Math.round(death.model_mae)} at the death` : ""}), and four totals in five land inside the range. Beats par in ${projectionSeasons.length} of ${SCORE_PROJECTION.backtest.length} seasons.`,
  },
  {
    key: "ball-outcome",
    model: "Ball outcome",
    predicts: "Dot, 1, 2, 3, 4, 6 or wicket for the next ball",
    result: `Log loss ${bo.model.log_loss.toFixed(4)}`,
    baseline: `${bo.baseline.log_loss.toFixed(4)} (phase and wickets frequencies)`,
    plain: `${pct(ballGain, 2)} sharper than league frequencies, and better in ${ballSeasons.length} of ${BALL_OUTCOME.backtest.length} seasons. A single ball is mostly luck, which is why head-to-head records need shrinking.`,
  },
  {
    key: "ratings",
    model: "CricIQ Ratings",
    predicts: "Where a player ranks among the regulars of the same seasons",
    result: `Shrunk record wins for ${ratingWins.length} of ${RATINGS.components.length} components`,
    baseline: "The raw record, taken at face value",
    plain: `Predicting each player's next season from ${RATINGS.splits.test_from}, blending a record with the average by how much its sample can be trusted beats trusting it raw on every rating component.`,
  },
  {
    key: "simulator",
    model: "Match simulator",
    predicts: "10,000 complete matches between two XIs",
    result: `${pct(sim.first_innings.coverage_80, 0)} of totals inside the 80% range · pre-match Brier ${sim.win.simulator.brier.toFixed(3)}`,
    baseline: `80% · coin flip ${sim.win.coin_flip.brier.toFixed(3)}`,
    plain: `Simulated scores spread like real ones (PIT χ² ${sim.first_innings.pit_chi2.toFixed(1)}, under the ${sim.first_innings.pit_chi2_critical.toFixed(1)} threshold), but before a ball is bowled it picks the winner no better than a coin flip, and says so.`,
  },
];

function ResultsTable() {
  const th = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";
  return (
    <div className="overflow-x-auto" {...scrollRegion("Every model against its baseline")}>
      <table className="w-full min-w-[52rem] text-sm">
        <caption className="sr-only">
          Every model against its baseline on the {testSeasons} test seasons
        </caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={th}>
              Model
            </th>
            <th scope="col" className={th}>
              CricIQ
            </th>
            <th scope="col" className={th}>
              Baseline
            </th>
            <th scope="col" className={th}>
              In plain words
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border align-top">
          {ROWS.map((r) => (
            <tr key={r.key}>
              <th scope="row" className="w-48 px-3 py-3 text-left font-normal">
                <Link
                  href={`/models?tab=${r.key}`}
                  className="font-medium underline-offset-4 hover:text-primary hover:underline"
                >
                  {r.model}
                </Link>
                <span className="mt-0.5 block text-xs text-muted-foreground">{r.predicts}</span>
              </th>
              <td className="w-56 px-3 py-3 font-mono text-xs text-foreground tabular-nums">
                {r.result}
              </td>
              <td className="w-56 px-3 py-3 font-mono text-xs text-muted-foreground tabular-nums">
                {r.baseline}
              </td>
              <td className="px-3 py-3 text-xs leading-relaxed text-muted-foreground">{r.plain}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ROLE: Record<SplitRole, { label: string; className: string; style?: string }> = {
  train: { label: "Learned from", className: "bg-muted-foreground/35" },
  validation: { label: "Tuned on", className: "", style: "var(--chart-2)" },
  test: { label: "Tested once on", className: "", style: "var(--chart-3)" },
};

function rowLabel(split: ModelSplit): string {
  return split.roles.map((r) => `${ROLE[r.role].label} ${r.from}–${r.to}`).join("; ");
}

/** Seasons as columns, one row per model, each season coloured by its role. */
function SplitChart() {
  const splits = modelSplits();
  const last = WIN_PROBABILITY.splits.served_through;
  const seasons = Array.from({ length: last - FIRST_SEASON + 1 }, (_, i) => FIRST_SEASON + i);
  return (
    <figure className="flex flex-col gap-3">
      <ul
        className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground"
        aria-label="Legend"
      >
        {(Object.keys(ROLE) as SplitRole[]).map((role) => (
          <li key={role} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={cn("size-2.5 rounded-sm", ROLE[role].className)}
              style={ROLE[role].style ? { background: ROLE[role].style } : undefined}
            />
            {ROLE[role].label}
          </li>
        ))}
      </ul>
      <div className="flex flex-col gap-2">
        {splits.map((split) => (
          <div key={split.key} className="grid grid-cols-[7.5rem_1fr] items-center gap-3">
            <span className="truncate text-xs text-muted-foreground">{split.label}</span>
            <div
              className="flex h-5 gap-0.5"
              role="img"
              aria-label={`${split.label}: ${rowLabel(split)}`}
            >
              {seasons.map((season) => {
                const role = roleIn(split, season);
                return (
                  <span
                    key={season}
                    title={`${season}: ${role ? ROLE[role].label.toLowerCase() : "not used"}`}
                    className={cn("flex-1 rounded-[3px]", role ? ROLE[role].className : "bg-muted")}
                    style={role && ROLE[role].style ? { background: ROLE[role].style } : undefined}
                  />
                );
              })}
            </div>
          </div>
        ))}
        <div className="grid grid-cols-[7.5rem_1fr] gap-3 text-[11px] text-muted-foreground">
          <span />
          <span className="flex justify-between font-mono tabular-nums" aria-hidden="true">
            <span>{FIRST_SEASON}</span>
            <span>{Math.round((FIRST_SEASON + last) / 2)}</span>
            <span>{last}</span>
          </span>
        </div>
      </div>
      <figcaption className="text-xs leading-relaxed text-muted-foreground">
        After testing, each served model is refitted on every season through {last} with the
        settings chosen above, so the site uses everything it knows.
      </figcaption>
    </figure>
  );
}

const PRINCIPLES: { title: string; body: string }[] = [
  {
    title: "No peeking",
    body: "Every feature is built from that ball and earlier matches only. A test deletes and rewrites every later match and checks that no earlier feature changes.",
  },
  {
    title: "Split by season, never by ball",
    body: "Balls in a match share one result, so the honest sample is about 1,200 matches. Models learn from older seasons, are tuned on the next ones and are tested once on the latest.",
  },
  {
    title: "Calibration over accuracy",
    body: "Models are judged on log loss, Brier score and calibration: a 70% chance must come true about 70% of the time. Accuracy alone rewards overconfidence.",
  },
  {
    title: "Uncertainty from whole matches",
    body: "Intervals on every gain resample whole matches, not balls, so correlated balls cannot make a result look surer than it is.",
  },
  {
    title: "Gated releases",
    body: "Model versions are committed with their evaluation. A new version that is worse on the test seasons fails the gate; deploys only score, never retrain.",
  },
  {
    title: "Negative results published",
    body: "Player, venue and squad-strength features were built and rejected because they did not help. Momentum and clutch were tested and failed. All of it is shown.",
  },
];

function Metric({
  title,
  href,
  verdict,
  children,
}: {
  title: string;
  href: string;
  verdict: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col gap-2 rounded-xl border border-border p-4 transition-colors hover:border-primary/40 hover:bg-accent/40"
    >
      <span className="flex items-center justify-between gap-2">
        <span className="font-medium">{title}</span>
        <ArrowRight
          aria-hidden="true"
          className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
        />
      </span>
      <span className="text-xs font-medium text-foreground">{verdict}</span>
      <span className="text-xs leading-relaxed text-muted-foreground">{children}</span>
    </Link>
  );
}

function Registry() {
  const rows = [
    {
      name: "Win probability",
      version: WIN_PROBABILITY.version,
      data: WIN_PROBABILITY.data_version,
      trained: seasonSpan(WIN_PROBABILITY.trained_on.seasons),
      size: `${WIN_PROBABILITY.trained_on.matches.toLocaleString("en-IN")} matches`,
    },
    {
      name: "Score projection",
      version: SCORE_PROJECTION.version,
      data: SCORE_PROJECTION.data_version,
      trained: seasonSpan(SCORE_PROJECTION.trained_on.seasons),
      size: `${SCORE_PROJECTION.trained_on.innings.toLocaleString("en-IN")} innings`,
    },
    {
      name: "Ball outcome",
      version: BALL_OUTCOME.version,
      data: BALL_OUTCOME.data_version,
      trained: seasonSpan(BALL_OUTCOME.trained_on.seasons),
      size: `${BALL_OUTCOME.trained_on.balls.toLocaleString("en-IN")} balls`,
    },
    {
      name: "CricIQ Ratings",
      version: RATINGS.version,
      data: RATINGS.data_version,
      trained: seasonSpan(RATINGS.trained_on.seasons),
      size: `${RATINGS.components.length} components`,
    },
    {
      name: "Match simulator",
      version: SIMULATOR.version,
      data: SIMULATOR.data_version,
      trained: `tuned ${seasonSpan(SIMULATOR.valid)}`,
      size: `${SIMULATOR.matches} test matches`,
    },
  ];
  const th = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";
  const td = "px-3 py-2 font-mono text-xs tabular-nums";
  return (
    <div className="overflow-x-auto" {...scrollRegion("Model registry")}>
      <table className="w-full min-w-[36rem] text-sm">
        <caption className="sr-only">Served model versions</caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={th}>
              Model
            </th>
            <th scope="col" className={th}>
              Version
            </th>
            <th scope="col" className={th}>
              Served model fitted on
            </th>
            <th scope="col" className={th}>
              Size
            </th>
            <th scope="col" className={th}>
              Data version
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={r.name}>
              <th scope="row" className="px-3 py-2 text-left font-normal">
                {r.name}
              </th>
              <td className={td}>{r.version}</td>
              <td className={td}>{r.trained}</td>
              <td className={td}>{r.size}</td>
              <td className={cn(td, "text-muted-foreground")}>{r.data}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Model Insights' front page: every model's test result, how testing works, and the registry. */
export function ModelsOverview() {
  const tenths = PRESSURE.swing_check;
  const calm = tenths[0];
  const tense = tenths[tenths.length - 1];
  const batting = CLUTCH.roles.batting;
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Favourite goes on to win"
          value={pct(accuracy)}
          context={`Of balls in ${testSeasons}, when the win probability model favoured a side (baseline ${pct(baselineAccuracy)}).`}
        />
        <Stat
          label="Projection miss"
          value={`${sp.model.mae.toFixed(1)} runs`}
          context={`Median error of the first-innings projection after every ball (par: ${sp.par_baseline.mae.toFixed(1)}).`}
        />
        <Stat
          label="80% ranges that held"
          value={pct(sp.model.coverage80)}
          context="Projected first-innings totals inside their 80% range: the range means what it says."
        />
        <Stat
          label="Pre-match winner"
          value="Coin flip"
          context={`The simulator's pre-match Brier ${sim.win.simulator.brier.toFixed(3)} against ${sim.win.coin_flip.brier.toFixed(3)} for 50-50: T20 is that close, and the site says so.`}
        />
      </div>

      <Section
        id="overview-results"
        title={`Every model, tested once on ${testSeasons}`}
        lede="Each model is scored on seasons it never saw while being built, against the simplest sensible alternative. Lower log loss, Brier and error are better. Open any model for its calibration, season-by-season backtest and rejected features."
      >
        <ResultsTable />
      </Section>

      <Section
        id="overview-splits"
        title="Which seasons each model saw"
        lede="Every model learns from older seasons, has its settings chosen on the next ones, and is tested once on seasons kept back until the end."
      >
        <SplitChart />
      </Section>

      <Section
        id="overview-principles"
        title="How every number is tested"
        lede="The same rules apply to every model and metric on the site."
      >
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {PRINCIPLES.map((p) => (
            <li key={p.title} className="flex flex-col gap-1">
              <span className="text-sm font-medium">{p.title}</span>
              <span className="text-xs leading-relaxed text-muted-foreground">{p.body}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        id="overview-metrics"
        title="Custom metrics, put to the test"
        lede="CricIQ's own measures were each given a test they could fail. Two passed and became part of the replay; two failed and are reported as findings."
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric title="Pressure" href="/lab/pressure" verdict="Passed: in the replay">
            Leverage predicts how far the next ball moves the match: from {calm.leverage.toFixed(2)}
            × a typical ball expected and {calm.realised.value.toFixed(2)}× realised in the calmest
            tenth to {tense.leverage.toFixed(1)}× and {tense.realised.value.toFixed(1)}× in the
            tensest.
          </Metric>
          <Metric title="Momentum" href="/lab/momentum" verdict="Descriptive, not predictive">
            Across {MOMENTUM.states.toLocaleString("en-IN")} moments, a 10-point surge adds{" "}
            {MOMENTUM.runs_per_10_points.value.toFixed(2)} runs over the next two overs and no extra
            chance of winning ({MOMENTUM.result_per_10_points.value.toFixed(3)}). It is shown as
            what just happened.
          </Metric>
          <Metric title="Clutch" href="/lab/clutch" verdict="Failed: no rating">
            A batter&apos;s record under pressure in odd seasons predicts even seasons with r ={" "}
            {batting.split_half_r?.toFixed(2) ?? "—"}, below the {batting.reliable_r.toFixed(1)} the
            plan required for a rating.
          </Metric>
          <Metric title="Rivalries" href="/lab/rivalries" verdict="Form, not history">
            Past head-to-head records add nothing to form; even the side in better form wins only{" "}
            {RIVALRIES.favourite.win_pct?.toFixed(1) ?? "—"}% of meetings.
          </Metric>
        </div>
      </Section>

      <Section
        id="overview-registry"
        title="Model registry"
        lede="The versions serving the site. Each is committed with its evaluation and model card, and every ball on the site is scored by these exact versions."
      >
        <Registry />
      </Section>
    </div>
  );
}
