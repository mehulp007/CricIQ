import Link from "next/link";

import { BacktestChart, ReliabilityChart, SeriesLegend } from "@/components/models/charts";
import { Section, Stat, signed } from "@/components/models/section";
import { scrollRegion } from "@/lib/a11y";
import { competitionPath } from "@/lib/competitions";
import { inningsLabel } from "@/lib/format";
import {
  type BacktestRow,
  type TestModelSet,
  type TestProjectionInsights as ProjectionData,
  type TestWinProbabilityInsights as WinProbabilityData,
  seasonSpan,
} from "@/lib/models";

const th = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";
const td = "px-3 py-2 font-mono text-xs tabular-nums";

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

function count(value: number): string {
  return value.toLocaleString("en-IN");
}

/** The win probability's verdict against its baseline, from the 95% interval of the gain. */
export function testVerdict(data: WinProbabilityData): string {
  const gain = data.test.vs_baseline;
  if (gain.ci_low > 0) return "clearly better than the match state alone";
  if (gain.ci_high < 0) return "worse than the match state alone";
  return gain.improvement > 0
    ? "better than the match state alone on balance, though with this few Tests the 95% interval includes no difference"
    : "level with the match state alone";
}

/** Model Insights overview for Tests: every model against its baseline on the test years. */
export function TestOverview({ models }: { models: TestModelSet }) {
  const wpData = models.winProbability;
  const wp = wpData.test;
  const sp = models.scoreProjection.test;
  const bo = models.ballOutcome.test;
  const tested = seasonSpan(wpData.splits.test);
  const wins = wpData.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss).length;
  const ballGain = 1 - bo.model.log_loss / bo.baseline.log_loss;
  const ratingWins = models.ratings.components.filter(
    (r) => r.next_season.mse && r.next_season.mse.shrunk < r.next_season.mse.raw,
  );
  const rows = [
    {
      key: "win-probability",
      model: "Win probability",
      predicts: "The chances of a win, a draw and a defeat after every ball",
      result: `Log loss ${wp.model.log_loss.toFixed(3)} · Brier ${wp.model.brier.toFixed(3)}`,
      baseline: `${wp.baseline.log_loss.toFixed(3)} · ${wp.baseline.brier.toFixed(3)} (the match state alone)`,
      verdict: `${testVerdict(wpData).charAt(0).toUpperCase()}${testVerdict(wpData).slice(1)} (gain ${signed(wp.vs_baseline.improvement)}, 95% interval ${signed(wp.vs_baseline.ci_low)} to ${signed(wp.vs_baseline.ci_high)}). Better in ${wins} of ${wpData.backtest.length} backtest years.`,
    },
    {
      key: "score-projection",
      model: "Innings projection",
      predicts: "Every innings' final total, with an 80% range, after every ball",
      result: `Off by ${sp.model.mae.toFixed(1)} runs · 80% range holds ${pct(sp.model.coverage80)}`,
      baseline: `${sp.par_baseline.mae.toFixed(1)} runs · ${pct(sp.par_baseline.coverage80)} (par by innings and wickets)`,
      verdict:
        sp.model.mae < sp.par_baseline.mae
          ? `Over ${count(sp.innings)} innings a projection misses by about ${Math.round(sp.model.mae)} runs, against ${Math.round(sp.par_baseline.mae)} for par.`
          : `Over ${count(sp.innings)} innings it misses by about ${Math.round(sp.model.mae)} runs, no better than par (${Math.round(sp.par_baseline.mae)}).`,
    },
    {
      key: "ball-outcome",
      model: "Ball outcome",
      predicts: "Dot, 1, 2, 3, 4, 6 or wicket for the next ball",
      result: `Log loss ${bo.model.log_loss.toFixed(4)}`,
      baseline: `${bo.baseline.log_loss.toFixed(4)} (phase and wickets frequencies)`,
      verdict:
        ballGain > 0
          ? `${pct(ballGain, 2)} sharper than Tests' own frequencies over ${count(bo.model.balls)} balls.`
          : `No sharper than Tests' own frequencies over ${count(bo.model.balls)} balls.`,
    },
    {
      key: "ratings",
      model: "CricIQ Ratings",
      predicts: "Where a player ranks among the regulars of the same years",
      result: `Shrunk record wins for ${ratingWins.length} of ${models.ratings.components.length} components`,
      baseline: "The raw record, taken at face value",
      verdict: `Predicting each player's next year, blending a record with the average by how much its sample can be trusted beats trusting it raw on ${ratingWins.length} of ${models.ratings.components.length} components.`,
    },
  ];
  return (
    <div className="flex flex-col gap-10">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Trained on"
          value={`${count(wpData.trained_on.matches)} Tests`}
          context={`Men's Tests alone, from ${seasonSpan(wpData.trained_on.seasons)}: no limited-overs cricket is mixed in.`}
        />
        <Stat
          label="Test matches held back"
          value={String(wp.matches)}
          context={`Tests from ${tested} that no model saw while it was built: ${wp.outcomes.won} won and ${wp.outcomes.lost} lost by the side batting last, ${wp.outcomes.drawn} drawn.`}
        />
        <Stat
          label="Simulator"
          value="None"
          context="A Test turns on declarations and time. The chase calculator and the replay's chase what-if run the win probability model instead."
        />
      </div>
      <Section
        id="test-results-heading"
        title="How the models did on Tests"
        lede={`Each model on the ${tested} test matches against a simple baseline, whichever way it came out. The tabs show how each was built and tested.`}
      >
        <div className="overflow-x-auto" {...scrollRegion("Every model on Tests")}>
          <table className="w-full min-w-[52rem] text-sm">
            <caption className="sr-only">Every Test model against its baseline</caption>
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
              {rows.map((r) => (
                <tr key={r.key}>
                  <th scope="row" className="w-48 px-3 py-3 text-left font-normal">
                    <Link
                      href={competitionPath("test", `/models?tab=${r.key}`)}
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
                  <td className="px-3 py-3 text-xs leading-relaxed text-muted-foreground">
                    {r.verdict}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

/** The Test win probability: three outcomes per innings, against the match state alone. */
export function TestWinProbabilityInsights({ data }: { data: WinProbabilityData }) {
  const t = data.test;
  const wins = data.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss).length;
  const outcomes = [
    ["won", "The batting side wins"],
    ["drawn", "A draw"],
    ["lost", "The batting side loses"],
  ] as const;
  return (
    <div className="flex flex-col gap-8">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Log loss on the test years"
          value={t.model.log_loss.toFixed(3)}
          context={`Against ${t.baseline.log_loss.toFixed(3)} for the match state alone, over ${t.matches} Tests (lower is better).`}
        />
        <Stat
          label="Gain over the baseline"
          value={signed(t.vs_baseline.improvement)}
          context={`95% interval ${signed(t.vs_baseline.ci_low)} to ${signed(t.vs_baseline.ci_high)}, resampling whole Tests: ${testVerdict(data)}.`}
        />
        <Stat
          label="Backtest"
          value={`${wins} of ${data.backtest.length}`}
          context="Years in which it beat the baseline, each fitted on every earlier year."
        />
      </div>

      <Section
        id="test-wp-how"
        title="How it works"
        lede="A Test can be won, lost or drawn, and a draw is what happens when time runs out. So the model gives three chances that add up to 100%, for the side batting at the time."
      >
        <div className="flex max-w-3xl flex-col gap-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            One multinomial regression per innings, on the match state: the lead (in the fourth
            innings, the runs needed and the rate they need), wickets in hand, the overs left and
            the scoring era (runs per wicket over the previous 40 Tests). On top of it, context
            known before the match, where it earned its place, each entered as itself and scaled by
            the share of the match still to play.
          </p>
          <p>
            Cricsheet has no session or time-of-day data, so the overs left are estimated as five
            days of 90 overs less the overs bowled. That ignores rain, bad light and the breaks
            between innings (drawn Tests in the data averaged 361 overs, not 450); the model learns
            how much of the nominal time is really left, but cannot know about a washed-out day.
          </p>
        </div>
        <div className="mt-5 overflow-x-auto" {...scrollRegion("Context per innings")}>
          <table className="w-full min-w-[32rem] text-sm">
            <caption className="sr-only">The context each innings&apos; model adds</caption>
            <thead className="border-b border-border">
              <tr>
                <th scope="col" className={th}>
                  Innings
                </th>
                <th scope="col" className={th}>
                  Context added to the match state
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {Object.entries(data.groups).map(([n, groups]) => (
                <tr key={n}>
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {inningsLabel(Number(n), false)}
                  </th>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {groups.map((g) => g.label).join(", ") || "None: the match state alone"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 max-w-3xl text-xs leading-relaxed text-muted-foreground">
          Each group was added while it lowered the log loss of a rolling origin over{" "}
          {seasonSpan(data.selection_years)} (each year predicted from every earlier year). About 40
          Tests are played a year, too few to choose on two validation years alone.
        </p>
      </Section>

      <Section
        id="test-wp-results"
        title="Results on the test years"
        lede={`Fitted on every Test before ${data.splits.test[0]} and scored once on ${seasonSpan(data.splits.test)}.`}
      >
        <div className="overflow-x-auto" {...scrollRegion("Results by innings")}>
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="sr-only">Log loss by innings, model and baseline</caption>
            <thead className="border-b border-border">
              <tr>
                <th scope="col" className={th}>
                  Innings
                </th>
                <th scope="col" className={th}>
                  Model log loss
                </th>
                <th scope="col" className={th}>
                  Baseline
                </th>
                <th scope="col" className={th}>
                  Balls
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {t.by_innings.map((r) => (
                <tr key={r.innings_no}>
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {inningsLabel(r.innings_no, false)}
                  </th>
                  <td className={td}>{r.model.log_loss.toFixed(4)}</td>
                  <td className={`${td} text-muted-foreground`}>
                    {r.baseline.log_loss.toFixed(4)}
                  </td>
                  <td className={`${td} text-muted-foreground`}>{count(r.rows)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-5 overflow-x-auto" {...scrollRegion("Results by day")}>
          <table className="w-full min-w-[30rem] text-sm">
            <caption className="sr-only">Log loss by estimated day, model and baseline</caption>
            <thead className="border-b border-border">
              <tr>
                <th scope="col" className={th}>
                  Day (estimated)
                </th>
                <th scope="col" className={th}>
                  Model log loss
                </th>
                <th scope="col" className={th}>
                  Baseline
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {t.by_day.map((r) => (
                <tr key={r.day}>
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    Day {r.day}
                  </th>
                  <td className={td}>{r.model_log_loss.toFixed(4)}</td>
                  <td className={`${td} text-muted-foreground`}>
                    {r.baseline_log_loss.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        id="test-wp-calibration"
        title="Calibration"
        lede="For each outcome, the chance the model gave against how often it happened, in bins of the predicted chance. Points on the diagonal are well calibrated."
      >
        <SeriesLegend baseline="Match state alone" />
        <div className="mt-4 grid gap-6 lg:grid-cols-3">
          {outcomes.map(([key, label]) => (
            <div key={key}>
              <p className="text-sm font-medium">{label}</p>
              <p className="text-xs text-muted-foreground">
                Off by {(100 * t.calibration[key].ece).toFixed(1)} points on average.
              </p>
              <ReliabilityChart
                model={t.calibration[key].bins}
                baseline={t.baseline_calibration[key].bins}
              />
            </div>
          ))}
        </div>
      </Section>

      <Section
        id="test-wp-backtest"
        title="Backtest"
        lede="Each year predicted by a model fitted on every earlier year, against the baseline fitted the same way."
      >
        <SeriesLegend baseline="Match state alone" />
        <BacktestChart rows={data.backtest as unknown as BacktestRow[]} />
      </Section>

      {data.alternatives.length > 0 && (
        <Section
          id="test-wp-trees"
          title="Why not boosted trees"
          lede="The limited-overs models are boosted trees. For Tests they were fitted on the same features and the same rolling origin."
        >
          <ul className="flex max-w-xl flex-col divide-y divide-border text-sm">
            {data.alternatives.map((a) => (
              <li key={a.model} className="flex justify-between gap-4 py-2">
                <span className="capitalize">{a.model}</span>
                <span className="font-mono tabular-nums">{a.log_loss.toFixed(4)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 max-w-3xl text-xs leading-relaxed text-muted-foreground">
            Every ball of a Test shares one result and there are only about 800 Tests, so trees
            split on the context that is the same for a whole match and memorise individual Tests. A
            regression cannot.
          </p>
        </Section>
      )}

      {data.swings.length > 0 && (
        <Section
          id="swings-heading"
          title="The biggest swings in Test history"
          lede="The single ball that moved the expected result most (a win counts 1, a draw a half) in each Test, largest first. The match's last ball is left out."
        >
          <ol className="flex flex-col divide-y divide-border">
            {data.swings.map((s) => (
              <li key={`${s.match_id}-${s.innings_no}-${s.seq_no}`}>
                <Link
                  href={competitionPath(
                    "test",
                    `/matches/${s.match_id}?ball=${s.innings_no}.${s.seq_no}`,
                  )}
                  className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-3 text-sm hover:text-primary"
                >
                  <span className="w-16 font-mono font-semibold text-positive tabular-nums">
                    +{s.swing.toFixed(0)} pts
                  </span>
                  <span className="min-w-0 flex-1">{s.description}</span>
                  <span className="text-xs text-muted-foreground">
                    {s.teams}, {s.season} · innings {s.innings_no}, ball {s.ball_label} · {s.result}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </Section>
      )}
    </div>
  );
}

/** The Test innings projection: every innings' final total, against par. */
export function TestProjectionInsights({ data }: { data: ProjectionData }) {
  const t = data.test;
  const wins = data.backtest.filter((r) => r.model_pinball < r.par_pinball).length;
  return (
    <div className="flex flex-col gap-8">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Typical miss"
          value={`${t.model.mae.toFixed(0)} runs`}
          context={`Mean distance of the median from the final total, against ${t.par_baseline.mae.toFixed(0)} for par, over ${count(t.innings)} innings.`}
        />
        <Stat
          label="80% range holds"
          value={pct(t.model.coverage80)}
          context={`Of final totals on the test years; about ${Math.round(t.model.width80)} runs wide on average.`}
        />
        <Stat
          label="Backtest"
          value={`${wins} of ${data.backtest.length}`}
          context="Years in which it beat par on pinball loss."
        />
      </div>
      <Section
        id="test-sp-how"
        title="How it works"
        lede="Where the innings being played will finish: an innings ends when the side is bowled out, declares, reaches a fourth-innings target or runs out of time, and the model learns all of these from history."
      >
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
          One LightGBM quantile model per level predicts the runs still to come, from the score,
          wickets in hand, the innings so far and its last ten overs, the lead, the overs left in
          the match, the innings number, the scoring era, the batting still to come and the fielding
          side&apos;s bowling. Conformal shifts measured on held-out years (
          {seasonSpan(data.splits.calibrate)} for the test) make each level hold about its share of
          totals. Par is the runs still to come at each quantile, by innings and wickets down.
        </p>
      </Section>
      <Section
        id="test-sp-results"
        title="Results on the test years"
        lede={`Scored once on ${seasonSpan(data.splits.test)}.`}
      >
        <div className="overflow-x-auto" {...scrollRegion("Projection by innings")}>
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="sr-only">Projection errors by innings</caption>
            <thead className="border-b border-border">
              <tr>
                <th scope="col" className={th}>
                  Innings
                </th>
                <th scope="col" className={th}>
                  Model miss
                </th>
                <th scope="col" className={th}>
                  Par miss
                </th>
                <th scope="col" className={th}>
                  80% range holds
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {t.by_innings.map((r) => (
                <tr key={r.innings_no}>
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {inningsLabel(r.innings_no, false)}
                  </th>
                  <td className={td}>{r.model.mae.toFixed(1)} runs</td>
                  <td className={`${td} text-muted-foreground`}>
                    {r.par_baseline.mae.toFixed(1)} runs
                  </td>
                  <td className={`${td} text-muted-foreground`}>{pct(r.model.coverage80)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section
        id="test-sp-backtest"
        title="Backtest"
        lede="Each year: fitted on the years before the previous two, calibrated on those two."
      >
        <div className="overflow-x-auto" {...scrollRegion("Projection backtest")}>
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="sr-only">Pinball loss by year, model and par</caption>
            <thead className="border-b border-border">
              <tr>
                <th scope="col" className={th}>
                  Year
                </th>
                <th scope="col" className={th}>
                  Pinball (model)
                </th>
                <th scope="col" className={th}>
                  Pinball (par)
                </th>
                <th scope="col" className={th}>
                  80% range holds
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.backtest.map((r) => (
                <tr key={r.season}>
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {r.season}
                  </th>
                  <td className={td}>{r.model_pinball.toFixed(2)}</td>
                  <td className={`${td} text-muted-foreground`}>{r.par_pinball.toFixed(2)}</td>
                  <td className={`${td} text-muted-foreground`}>{pct(r.coverage80)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
