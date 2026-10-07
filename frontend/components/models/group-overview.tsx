import Link from "next/link";

import { Section, Stat } from "@/components/models/section";
import { scrollRegion } from "@/lib/a11y";
import { competitionPath, getCompetition, phrase, possessive } from "@/lib/competitions";
import { type Bootstrap, type ModelSet, seasonSpan } from "@/lib/models";

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

function count(value: number): string {
  return value.toLocaleString("en-IN");
}

const LEAGUE_NAMES: Record<string, string> = {
  BBL: "BBL",
  CPL: "CPL",
  PSL: "PSL",
  SA20: "SA20",
};

function names(ids: string[]): string {
  const labels = ids.map((id) => LEAGUE_NAMES[id] ?? id);
  return labels.length > 1
    ? `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`
    : labels[0];
}

/** The pooled T20 model's log loss against the group's own on the same test matches. */
export function tradeOff(pooled: number, own: number, alone: string): string {
  const gap = own - pooled;
  if (Math.abs(gap) < 0.005) return "about the same.";
  return gap > 0
    ? `learning from ${alone} alone costs some accuracy here.`
    : `the model trained on ${alone} alone does better here.`;
}

/** A win probability verdict that says which way it came out, and how sure that is. */
export function winProbabilityVerdict(gain: Bootstrap, matches: number): string {
  const interval = `95% interval ${gain.ci_low.toFixed(3)} to ${gain.ci_high.toFixed(3)}`;
  if (gain.ci_low > 0) {
    return `Better than the baseline over ${matches} test matches (gain ${gain.improvement.toFixed(3)}, ${interval}).`;
  }
  if (gain.ci_high < 0) {
    return `Worse than the baseline over ${matches} test matches (${gain.improvement.toFixed(3)}, ${interval}).`;
  }
  return `Level with the baseline over ${matches} test matches: ${gain.improvement > 0 ? "ahead" : "behind"} by ${Math.abs(gain.improvement).toFixed(3)}, but the ${interval} includes no difference, so a logistic regression on the score, wickets and balls left does about as well.`;
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
 * Model Insights for a competition whose model group has several competitions (the
 * T20 leagues): models trained on the group's competitions only, and how they did on
 * this competition's own test matches, whichever way it came out.
 */
export function GroupOverview({ models }: { models: ModelSet }) {
  const c = getCompetition(models.competition);
  const on = phrase(models.competition);
  const own = possessive(models.competition);
  const { winProbability: wp, scoreProjection: sp, ballOutcome: bo } = models.results;
  const tested = seasonSpan(models.winProbability.splits.test);
  const matches = (models.winProbability.trained_on as unknown as { matches: number }).matches;
  const pooled = models.pooledWinProbability;
  const rows: Row[] = [];
  if (wp?.baseline && wp.vs_baseline) {
    rows.push({
      key: "win-probability",
      model: "Win probability",
      result: `Log loss ${wp.model.log_loss.toFixed(3)} · AUC ${(wp.model.auc ?? 0).toFixed(2)}`,
      baseline: `${wp.baseline.log_loss.toFixed(3)} · ${(wp.baseline.auc ?? 0).toFixed(2)} (logistic regression on the match state)`,
      verdict: winProbabilityVerdict(wp.vs_baseline, wp.matches ?? 0),
    });
  }
  if (sp?.par_baseline) {
    rows.push({
      key: "score-projection",
      model: "Score projection",
      result: `Median error ${sp.model.mae.toFixed(1)} runs · 80% range holds ${pct(sp.model.coverage80)}`,
      baseline: `${sp.par_baseline.mae.toFixed(1)} runs · ${pct(sp.par_baseline.coverage80)} (par for the era)`,
      verdict:
        sp.model.mae < sp.par_baseline.mae
          ? `Over ${count(sp.model.innings)} first innings, a projection misses by about ${Math.round(sp.model.mae)} runs, against ${Math.round(sp.par_baseline.mae)} for par.`
          : `Over ${count(sp.model.innings)} first innings it misses by about ${Math.round(sp.model.mae)} runs, no better than par (${Math.round(sp.par_baseline.mae)}).`,
    });
  }
  if (bo?.baseline) {
    const gain = 1 - bo.model.log_loss / bo.baseline.log_loss;
    rows.push({
      key: "ball-outcome",
      model: "Ball outcome",
      result: `Log loss ${bo.model.log_loss.toFixed(4)}`,
      baseline: `${bo.baseline.log_loss.toFixed(4)} (phase and wickets frequencies)`,
      verdict:
        gain > 0
          ? `${pct(gain, 2)} sharper than the competition's own frequencies over ${count(bo.model.balls)} balls.`
          : `No sharper than the competition's own frequencies over ${count(bo.model.balls)} balls.`,
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
          value={`${count(matches)} matches`}
          context={`The ${names(models.trainedOn)} only: no IPL and no international matches. Each player's record counts these leagues alone, and each league keeps its own scoring era.`}
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
        lede={`Each model on ${own} own test matches (${tested}) against the same simple baseline it is judged by everywhere, whichever way it came out. The tabs show how each was built and its results on the four leagues together.`}
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
        id="group-why-heading"
        title="Models of the leagues' own"
        lede="Every kind of cricket on CricIQ is modelled from its own matches only."
      >
        <ul className="grid gap-4 text-sm leading-relaxed text-muted-foreground md:grid-cols-2">
          <li>
            <span className="font-medium text-foreground">Four leagues, one set of models.</span>{" "}
            The {names(models.trainedOn)} are trained together, so a player who has played in
            several has one record across them; the{" "}
            <Link
              href={competitionPath("ipl", "/models")}
              className="text-foreground underline-offset-4 hover:underline"
            >
              IPL
            </Link>{" "}
            and{" "}
            <Link
              href={competitionPath("t20i", "/models")}
              className="text-foreground underline-offset-4 hover:underline"
            >
              T20Is
            </Link>{" "}
            have models of their own.
          </li>
          {pooled && wp && (
            <li>
              <span className="font-medium text-foreground">The trade-off.</span> Before these
              models, one model trained on every T20 competition, IPL and internationals included,
              served {on}. On these test matches its win probability scored{" "}
              {pooled.model.log_loss.toFixed(3)} against {wp.model.log_loss.toFixed(3)} now (lower
              is better): {tradeOff(pooled.model.log_loss, wp.model.log_loss, "the leagues")}
              {wp.model.log_loss - pooled.model.log_loss >= 0.005 &&
                " That model also counted each player's IPL and international record."}
            </li>
          )}
          <li>
            <span className="font-medium text-foreground">Ratings on {own} own records.</span>{" "}
            CricIQ Ratings are fitted on {own} records alone, so a player is rated among its
            regulars.{" "}
            {borrowed.length > 0
              ? `${borrowed.length} of ${models.ratings.components.length} components follow too few players to estimate their own shrinkage and borrow the four leagues' records together.`
              : "Every component has enough players to estimate its own shrinkage."}
          </li>
          <li>
            <span className="font-medium text-foreground">Small samples, honest intervals.</span> A
            league&apos;s test seasons can be a few dozen matches, so a model only counts as better
            (or worse) than its baseline here when the whole 95% interval says so.
          </li>
        </ul>
      </Section>
    </div>
  );
}
