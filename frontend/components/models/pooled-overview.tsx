import Link from "next/link";

import { Section, Stat } from "@/components/models/section";
import { scrollRegion } from "@/lib/a11y";
import { competitionPath, getCompetition, phrase, possessive } from "@/lib/competitions";
import { IPL_COMPARISON, type ModelSet, seasonSpan } from "@/lib/models";

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

function count(value: number): string {
  return value.toLocaleString("en-IN");
}

/** What the simulator's backtest of this competition found. */
function simulatorNote(models: ModelSet): string {
  const b = models.simulatorBacktest;
  if (!b) return "The match simulator has not been backtested here yet.";
  const first = b.first_innings;
  const totals = `its 80% range held ${pct(first.coverage_80, 0)} of ${first.matches} first-innings totals (${first.simulated_mean} simulated on average, ${first.actual_mean} actual)`;
  return models.simulator
    ? `Backtested on ${seasonSpan(b.test)}: ${totals}, and the totals' spread passed the gate.`
    : `Backtested on ${seasonSpan(b.test)}: ${totals}, and the gate found that the ${b.gate.join("; ")}, so it is not served.`;
}

interface Row {
  key: string;
  model: string;
  result: string;
  baseline: string;
  verdict: string;
}

/**
 * Model Insights for a competition served by the pooled T20 models: how they did
 * on this competition's own test matches, and what it has of each model.
 */
export function PooledOverview({ models }: { models: ModelSet }) {
  const c = getCompetition(models.competition);
  const on = phrase(models.competition);
  const own = possessive(models.competition);
  const { winProbability: wp, scoreProjection: sp, ballOutcome: bo } = models.results;
  const tested = seasonSpan(models.winProbability.splits.test);
  const trained = models.winProbability.trained_on as unknown as {
    competitions: string[];
    matches: number;
  };
  const rows: Row[] = [];
  if (wp?.baseline && wp.vs_baseline) {
    const g = wp.vs_baseline;
    rows.push({
      key: "win-probability",
      model: "Win probability",
      result: `Log loss ${wp.model.log_loss.toFixed(3)} · AUC ${(wp.model.auc ?? 0).toFixed(2)}`,
      baseline: `${wp.baseline.log_loss.toFixed(3)} · ${(wp.baseline.auc ?? 0).toFixed(2)} (logistic regression on the match state)`,
      verdict:
        g.ci_low > 0
          ? `Better than the baseline over ${wp.matches} test matches (gain ${g.improvement.toFixed(3)}, 95% interval ${g.ci_low.toFixed(3)} to ${g.ci_high.toFixed(3)}).`
          : `Ahead of the baseline over ${wp.matches} test matches, but the 95% interval (${g.ci_low.toFixed(3)} to ${g.ci_high.toFixed(3)}) includes no gain: too few matches to be sure.`,
    });
  }
  if (sp?.par_baseline) {
    rows.push({
      key: "score-projection",
      model: "Score projection",
      result: `Median error ${sp.model.mae.toFixed(1)} runs · 80% range holds ${pct(sp.model.coverage80)}`,
      baseline: `${sp.par_baseline.mae.toFixed(1)} runs · ${pct(sp.par_baseline.coverage80)} (par for the era)`,
      verdict: `Over ${count(sp.model.innings)} first innings, a projection misses by about ${Math.round(sp.model.mae)} runs, against ${Math.round(sp.par_baseline.mae)} for par.`,
    });
  }
  if (bo?.baseline) {
    rows.push({
      key: "ball-outcome",
      model: "Ball outcome",
      result: `Log loss ${bo.model.log_loss.toFixed(4)}`,
      baseline: `${bo.baseline.log_loss.toFixed(4)} (phase and wickets frequencies)`,
      verdict: `${pct(1 - bo.model.log_loss / bo.baseline.log_loss, 2)} sharper than the competition's own frequencies over ${count(bo.model.balls)} balls.`,
    });
  }
  const borrowed = models.ratings.components.filter(
    (r) => (r as { borrowed?: string | null }).borrowed,
  );
  const th = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";

  return (
    <div className="flex flex-col gap-10">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Trained on"
          value={`${count(trained.matches)} matches`}
          context={`Every T20 competition at once (${trained.competitions.join(", ")}), with each player's record shared across them and each competition's own scoring era.`}
        />
        <Stat
          label={`${c.label} test matches`}
          value={wp ? String(wp.matches) : "–"}
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
          context={simulatorNote(models)}
        />
      </div>

      <Section
        id="competition-results-heading"
        title={`How the models did on ${on}`}
        lede={`Each model on ${own} own test matches (${tested}) against the same simple baseline it is judged by everywhere. The tabs show how each was built and its results on every competition together.`}
      >
        <div className="overflow-x-auto" {...scrollRegion(`Every model on ${on}`)}>
          <table className="w-full min-w-[48rem] text-sm">
            <caption className="sr-only">
              Every model against its baseline on {own} {tested} test matches
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
                  <th scope="row" className="w-44 px-3 py-3 text-left font-normal">
                    <Link
                      href={competitionPath(models.competition, `/models?tab=${r.key}`)}
                      className="font-medium underline-offset-4 hover:text-primary hover:underline"
                    >
                      {r.model}
                    </Link>
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

      <Section
        id="pooled-why-heading"
        title="One model for all T20 cricket"
        lede="Why these models are shared, and why the IPL keeps its own."
      >
        <ul className="grid gap-4 text-sm leading-relaxed text-muted-foreground md:grid-cols-2">
          <li>
            <span className="font-medium text-foreground">More evidence per player.</span> A
            player&apos;s record counts every T20 competition they played in, so a batter new to{" "}
            {on} arrives with their record from elsewhere. Each competition keeps its own scoring
            era, so a total is judged against its own conditions.
          </li>
          <li>
            <span className="font-medium text-foreground">The IPL keeps its own models.</span>{" "}
            Pooling was only worth it for the IPL if it predicted the IPL at least as well. On the
            IPL&apos;s own test balls it did not (win probability{" "}
            {IPL_COMPARISON.winProbability.better ? "better" : "worse"}, ball outcome{" "}
            {IPL_COMPARISON.ballOutcome.better ? "better" : "worse"}, score projection outside its
            coverage band), so the{" "}
            <Link
              href={competitionPath("ipl", "/models")}
              className="text-foreground underline-offset-4 hover:underline"
            >
              IPL&apos;s models
            </Link>{" "}
            are its own.
          </li>
          <li>
            <span className="font-medium text-foreground">Ratings on {own} own records.</span>{" "}
            CricIQ Ratings are fitted on {own} records alone, so a player is rated among its
            regulars.{" "}
            {borrowed.length > 0
              ? `${borrowed.length} of ${models.ratings.components.length} components follow too few players to estimate their own shrinkage and borrow all-T20 cricket's.`
              : "Every component has enough players to estimate its own shrinkage."}
          </li>
          <li>
            <span className="font-medium text-foreground">Small samples, honest intervals.</span> A
            competition&apos;s test seasons can be a few dozen matches, so a model only counts as
            better than its baseline here when the whole 95% interval says so.
          </li>
        </ul>
      </Section>
    </div>
  );
}
