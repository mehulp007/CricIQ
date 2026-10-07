import Link from "next/link";

import { tradeOff, winProbabilityVerdict } from "@/components/models/group-overview";
import { Section, Stat } from "@/components/models/section";
import { scrollRegion } from "@/lib/a11y";
import { type CompetitionId, competitionPath, getCompetition, phrase } from "@/lib/competitions";
import { type ModelSet, favouriteAccuracy, seasonSpan } from "@/lib/models";

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

function count(value: number): string {
  return value.toLocaleString("en-IN");
}

interface Row {
  key: string;
  model: string;
  predicts: string;
  result: string;
  baseline: string;
  verdict: string;
}

/** What the simulator's backtest found, served or not. */
function simulatorRow(models: ModelSet): Row | null {
  const b = models.simulatorBacktest;
  if (!b) return null;
  const first = b.first_innings;
  return {
    key: "simulator",
    model: "Match simulator",
    predicts: "10,000 complete matches between two XIs",
    result: `${pct(first.coverage_80, 0)} of totals inside the 80% range · pre-match Brier ${b.win.simulator.brier.toFixed(3)}`,
    baseline: `80% · coin flip ${b.win.coin_flip.brier.toFixed(3)}`,
    verdict: models.simulator
      ? `Simulated first-innings totals averaged ${first.simulated_mean} against ${first.actual_mean} and spread like real ones (PIT χ² ${first.pit_chi2.toFixed(1)}, under the ${first.pit_chi2_critical.toFixed(1)} threshold), so it is served.`
      : `Simulated first-innings totals averaged ${first.simulated_mean} against ${first.actual_mean}, and the gate found that the ${b.gate.join("; ")}, so it is not served.`,
  };
}

/** Why a competition's models are its own, for the "Trained on" card. */
const OWN_MODELS: Partial<Record<CompetitionId, string>> = {
  odi: "a 50-over match is its own game, so it has its own models.",
  t20i: "no league matches, so a player's record counts their international cricket only.",
};

/**
 * Model Insights for a competition with models of its own (T20Is, ODIs): every model
 * against its baseline on the test years, stated whichever way it came out.
 */
export function FormatOverview({ models }: { models: ModelSet }) {
  const c = getCompetition(models.competition);
  const on = phrase(models.competition);
  const wpData = models.winProbability;
  const wp = wpData.test;
  const sp = models.scoreProjection.test;
  const bo = models.ballOutcome.test;
  const tested = seasonSpan(wpData.splits.test);
  const pooled = models.pooledWinProbability;
  const gain = wp.vs_baseline;
  // Better only when the whole 95% interval of the gain is above zero.
  const wpBetter = gain.ci_low > 0;
  const wpSeasons = wpData.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss);
  const spBetter = sp.model.mae < sp.par_baseline.mae;
  const ballGain = 1 - bo.model.log_loss / bo.baseline.log_loss;
  const ratingWins = models.ratings.components.filter(
    (r) => r.next_season.mse && r.next_season.mse.shrunk < r.next_season.mse.raw,
  );
  const rows: Row[] = [
    {
      key: "win-probability",
      model: "Win probability",
      predicts: "Each side's chance of winning after every ball",
      result: `Log loss ${wp.model.log_loss.toFixed(3)} · AUC ${(wp.model.auc ?? 0).toFixed(2)}`,
      baseline: `${wp.baseline.log_loss.toFixed(3)} · ${(wp.baseline.auc ?? 0).toFixed(2)} (logistic regression on the match state)`,
      verdict: wpBetter
        ? `The side it favours goes on to win after ${pct(favouriteAccuracy(wp.reliability))} of balls, and its chances are off by ${(100 * wp.model.ece).toFixed(1)} points on average. Better than the baseline in ${wpSeasons.length} of ${wpData.backtest.length} backtest years.`
        : `${winProbabilityVerdict(gain, wp.matches)} It beat the baseline in ${wpSeasons.length} of ${wpData.backtest.length} backtest years, and its chances are off by ${(100 * wp.model.ece).toFixed(1)} points on average.`,
    },
    {
      key: "score-projection",
      model: "Score projection",
      predicts: "The first-innings total, with an 80% range, after every ball",
      result: `Median error ${sp.model.mae.toFixed(1)} runs · 80% range holds ${pct(sp.model.coverage80)}`,
      baseline: `${sp.par_baseline.mae.toFixed(1)} runs · ${pct(sp.par_baseline.coverage80)} (par for the era)`,
      verdict: spBetter
        ? `Over ${count(sp.model.innings)} first innings, a projection misses by about ${Math.round(sp.model.mae)} runs, against ${Math.round(sp.par_baseline.mae)} for par.`
        : `Over ${count(sp.model.innings)} first innings it misses by about ${Math.round(sp.model.mae)} runs, no better than par (${Math.round(sp.par_baseline.mae)}).`,
    },
    {
      key: "ball-outcome",
      model: "Ball outcome",
      predicts: "Dot, 1, 2, 3, 4, 6 or wicket for the next ball",
      result: `Log loss ${bo.model.log_loss.toFixed(4)}`,
      baseline: `${bo.baseline.log_loss.toFixed(4)} (phase and wickets frequencies)`,
      verdict:
        ballGain > 0
          ? `${pct(ballGain, 2)} sharper than ${on}' own frequencies over ${count(bo.model.balls)} balls.`
          : `No sharper than ${on}' own frequencies over ${count(bo.model.balls)} balls.`,
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
  const sim = simulatorRow(models);
  if (sim) rows.push(sim);
  const th = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";

  return (
    <div className="flex flex-col gap-10">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Trained on"
          value={`${count(wpData.trained_on.matches)} matches`}
          context={`${on} alone, from ${seasonSpan(wpData.trained_on.seasons)}: ${OWN_MODELS[models.competition] ?? "no other cricket is mixed in."}`}
        />
        <Stat
          label={`${c.label} test matches`}
          value={String(wp.matches)}
          context={`Matches from ${tested} that no model saw while it was built.`}
        />
        <Stat
          label="Simulator"
          value={
            models.simulator
              ? "Backtested, served"
              : models.simulatorBacktest
                ? "Failed its gate"
                : "Not backtested yet"
          }
          context={sim ? sim.verdict : "The match simulator has not been backtested here yet."}
        />
      </div>

      <Section
        id="format-results-heading"
        title={`How the models did on ${on}`}
        lede={`Each model on the ${tested} test matches against the same simple baseline it is judged by everywhere, whichever way it came out. The tabs show how each was built and tested.`}
      >
        <div className="overflow-x-auto" {...scrollRegion(`Every model on ${on}`)}>
          <table className="w-full min-w-[52rem] text-sm">
            <caption className="sr-only">
              Every model against its baseline on the {tested} test matches
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
              {rows.map((r) => (
                <tr key={r.key}>
                  <th scope="row" className="w-48 px-3 py-3 text-left font-normal">
                    <Link
                      href={competitionPath(models.competition, `/models?tab=${r.key}`)}
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
        {pooled && (
          <p className="mt-4 max-w-3xl text-xs leading-relaxed text-muted-foreground">
            Before these models, one model trained on every T20 competition, leagues included,
            served {on}. On the same test matches its win probability scored{" "}
            {pooled.model.log_loss.toFixed(3)} against {wp.model.log_loss.toFixed(3)} now (lower is
            better): {tradeOff(pooled.model.log_loss, wp.model.log_loss, on)}
          </p>
        )}
      </Section>
    </div>
  );
}
