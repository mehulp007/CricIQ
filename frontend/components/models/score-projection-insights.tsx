import {
  LevelCalibrationChart,
  ProjectionBacktestChart,
  SeriesLegend,
} from "@/components/models/charts";
import { Section, Stat } from "@/components/models/section";
import { Badge } from "@/components/ui/badge";
import { SCORE_PROJECTION as sp, SERIES, seasonSpan } from "@/lib/models";
import { scrollRegion } from "@/lib/a11y";

const PHASES = { powerplay: "Powerplay", middle: "Middle overs", death: "Death overs" } as const;

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function runs(value: number, signedValue = false): string {
  const text = Math.abs(value).toFixed(1);
  if (!signedValue) return text;
  return `${value >= 0 ? "+" : "−"}${text}`;
}

export function ScoreProjectionInsights() {
  const { test } = sp;
  const testSeasons = seasonSpan(sp.splits.test);
  const wins = sp.backtest.filter((r) => r.mae < r.par_mae).length;
  const biases = sp.backtest.map((r) => r.bias);
  const served = sp.feature_selection.find((r) => r.variant === "served")!;
  const candidates = sp.feature_selection.filter((r) => r.variant !== "served");
  const worst = Math.max(...candidates.map((r) => Math.abs(r.pinball - served.pinball)), 0.01);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="font-mono text-[11px] text-primary">
            Score projection v{sp.version}
          </Badge>
          <Badge variant="outline" className="font-mono text-[11px] text-muted-foreground">
            Trained on {seasonSpan(sp.trained_on.seasons)} ·{" "}
            {sp.trained_on.innings.toLocaleString("en-IN")} first innings
          </Badge>
        </div>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">
          During a first innings: the projected total, an 80% range and the odds of passing any
          score. Tested once on {test.model.innings} first innings from {testSeasons} that the model
          never saw. Chases are not projected: they stop at the target, and the win probability
          covers them.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="80% range covers"
          value={pct(test.model.coverage80)}
          context="of real totals on the test seasons. It should be 80%."
        />
        <Stat
          label="Median error"
          value={`${runs(test.model.mae)} runs`}
          context={`vs ${runs(test.par_baseline.mae)} for par for the era and ${runs(test.run_rate.mae)} for the TV run-rate projection.`}
        />
        <Stat
          label="Range width"
          value={`${runs(test.model.width80)} runs`}
          context={`Average width of the 80% range, vs ${runs(test.par_baseline.width80)} for par plus the historical spread.`}
        />
        <Stat
          label="Bias"
          value={`${runs(test.model.bias, true)} runs`}
          context="Median minus the actual total on the test seasons. Positive means it ran high."
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="levels-heading"
          title="Does the 90% line mean 90%?"
          lede={`Each quantile against the share of real totals in ${testSeasons} that finished at or below it. Points on the dashed diagonal are exactly calibrated.`}
        >
          <LevelCalibrationChart rows={test.model.level_calibration} />
        </Section>

        <Section
          id="projection-backtest-heading"
          title="Every season, not just the last two"
          lede={`Retrained on earlier seasons only, then scored season by season. The projection has the smaller median error in ${wins} of ${sp.backtest.length} seasons. Season bias ranges from ${runs(Math.min(...biases), true)} to ${runs(Math.max(...biases), true)} runs, with no drift in one direction as totals climbed.`}
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-xs text-muted-foreground">
              Median error in runs (lower is better)
            </span>
            <SeriesLegend baseline="Par + spread" />
          </div>
          <ProjectionBacktestChart rows={sp.backtest} />
        </Section>
      </div>

      <Section
        id="projection-compare-heading"
        title="Against simpler projections"
        lede={`The same ${test.model.rows.toLocaleString("en-IN")} first-innings moments. Pinball loss scores the whole distribution. The Brier score is for P(total ≥ X) at ${test.thresholds.join(", ")}.`}
      >
        <div className="overflow-x-auto" {...scrollRegion("Projection comparison")}>
          <table className="w-full min-w-xl text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Projection</th>
                <th className="py-2 pr-3 text-right font-medium">80% covers</th>
                <th className="py-2 pr-3 text-right font-medium">Median error</th>
                <th className="py-2 pr-3 text-right font-medium">Pinball</th>
                <th className="py-2 text-right font-medium">Brier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {[
                { label: "CricIQ projection (served)", m: test.model, strong: true },
                {
                  label: "Same model, without conformal calibration",
                  m: test.uncalibrated,
                  strong: false,
                },
                {
                  label: "Par for the era + historical spread",
                  m: test.par_baseline,
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
                  <td className="py-2.5 pr-3 text-right">{pct(m.coverage80)}</td>
                  <td className="py-2.5 pr-3 text-right">{m.mae.toFixed(2)}</td>
                  <td className="py-2.5 pr-3 text-right">{m.pinball.toFixed(3)}</td>
                  <td className="py-2.5 text-right">{m.threshold_brier.toFixed(3)}</td>
                </tr>
              ))}
              <tr className="text-muted-foreground">
                <th scope="row" className="py-2.5 pr-3 text-left font-sans font-normal">
                  TV run-rate projection (a single number)
                </th>
                <td className="py-2.5 pr-3 text-right">—</td>
                <td className="py-2.5 pr-3 text-right">{test.run_rate.mae.toFixed(2)}</td>
                <td className="py-2.5 pr-3 text-right">—</td>
                <td className="py-2.5 text-right">—</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="projection-phase-heading"
          title="Sharper as the innings goes on"
          lede="Median error and 80% coverage by phase on the test seasons. Early on, the honest range is wide; by the death overs it narrows to a couple of big hits either way."
        >
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-2 pr-3 font-medium">Phase</th>
                <th className="py-2 pr-3 text-right font-medium">Model</th>
                <th className="py-2 pr-3 text-right font-medium">Par</th>
                <th className="py-2 pr-3 text-right font-medium">Run rate</th>
                <th className="py-2 pr-3 text-right font-medium">Covers</th>
                <th className="py-2 text-right font-medium">Width</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {test.by_phase.map((r) => (
                <tr key={r.phase}>
                  <th scope="row" className="py-2.5 pr-3 text-left font-sans font-normal">
                    {PHASES[r.phase]}
                  </th>
                  <td className="py-2.5 pr-3 text-right">{r.model_mae.toFixed(1)}</td>
                  <td className="py-2.5 pr-3 text-right text-muted-foreground">
                    {r.par_mae.toFixed(1)}
                  </td>
                  <td className="py-2.5 pr-3 text-right text-muted-foreground">
                    {r.run_rate_mae.toFixed(1)}
                  </td>
                  <td className="py-2.5 pr-3 text-right">{pct(r.model_coverage80)}</td>
                  <td className="py-2.5 text-right text-muted-foreground">
                    {r.model_width80.toFixed(0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section
          id="projection-selection-heading"
          title="What didn't make the cut"
          lede={`Each candidate group was added to the model and scored season by season on ${seasonSpan(served.seasons)}, before the test seasons. None improved the pinball loss by more than 0.01 runs, so the simpler model stays.`}
        >
          <ul className="flex flex-col gap-3">
            {candidates.map((r) => {
              const delta = r.pinball - served.pinball;
              return (
                <li
                  key={r.variant}
                  className="grid gap-1.5 sm:grid-cols-[1fr_11rem] sm:items-center sm:gap-4"
                >
                  <span className="text-sm">{r.label.replace(/^\+ /, "")}</span>
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
                      {delta >= 0 ? "+" : "−"}
                      {Math.abs(delta).toFixed(3)}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Change in pinball loss (runs) when the group is added. Positive means worse.
          </p>
        </Section>
      </div>

      <Section
        id="projection-method-heading"
        title="How it works"
        lede="LightGBM quantile regression, conformally calibrated."
      >
        <ul className="grid gap-4 text-sm leading-relaxed text-muted-foreground md:grid-cols-2">
          <li>
            <span className="font-medium text-foreground">Runs relative to the era.</span> The model
            predicts the runs still to come as a share of what the era&apos;s scoring rate would
            give from the balls left. One model then works from 2008 to 2026, while average totals
            rose by 30 runs.
          </li>
          <li>
            <span className="font-medium text-foreground">A whole distribution.</span> Seven
            quantile models (5% to 95%) give the median, the 80% range and the chance of passing any
            total. The same numbers drive the fan on the worm chart.
          </li>
          <li>
            <span className="font-medium text-foreground">Honest ranges.</span> Conformal
            calibration shifts each quantile until that share of held-out totals falls below it.
            Tuning, calibration and testing each use different seasons.
          </li>
          <li>
            <span className="font-medium text-foreground">Limits.</span> The range is calibrated on
            average, so it runs a little narrow early and a little wide late. Pitch, weather and
            team news are not in the data. Rain-shortened innings are not projected.
          </li>
        </ul>
      </Section>
    </div>
  );
}
