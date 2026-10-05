import Link from "next/link";

import { Section, Stat } from "@/components/models/section";
import { scrollRegion } from "@/lib/a11y";
import { type CalibrationRow, SIMULATOR as s, seasonSpan } from "@/lib/models";

const COLOR = "var(--chart-3)";

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

function signed(value: number, digits = 3): string {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}`;
}

/** Actual totals' percentiles within their simulations, in tenths: flat is calibrated. */
function PitChart() {
  const counts = s.first_innings.pit_counts;
  const expected = s.first_innings.matches / counts.length;
  const top = Math.max(...counts, expected) * 1.15;
  return (
    <figure className="flex flex-col gap-2">
      <div
        className="relative flex h-40 items-end gap-1.5 border-b border-border"
        role="img"
        aria-label={`Matches per tenth of the simulated distribution: ${counts.join(", ")}; ${expected.toFixed(0)} each if perfectly calibrated`}
      >
        <span
          aria-hidden="true"
          className="absolute inset-x-0 border-t border-dashed border-muted-foreground/60"
          style={{ bottom: `${(100 * expected) / top}%` }}
        />
        {counts.map((c, i) => (
          <span
            key={i}
            aria-hidden="true"
            className="flex-1 rounded-t-sm"
            style={{ height: `${(100 * c) / top}%`, background: COLOR, opacity: 0.85 }}
          />
        ))}
      </div>
      <figcaption className="flex justify-between text-[11px] text-muted-foreground">
        <span>Actual total far below the simulation</span>
        <span>far above</span>
      </figcaption>
    </figure>
  );
}

function CalibrationTable({ rows, label }: { rows: CalibrationRow[]; label: string }) {
  const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
  const td = "px-2 py-2 text-right font-mono tabular-nums";
  return (
    <div className="overflow-x-auto" {...scrollRegion(label)}>
      <table className="w-full min-w-[20rem] text-sm">
        <caption className="sr-only">{label}</caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={`${th} text-left`}>
              Fifth
            </th>
            <th scope="col" className={th}>
              Matches
            </th>
            <th scope="col" className={th}>
              Simulated
            </th>
            <th scope="col" className={th}>
              Happened
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r, i) => (
            <tr key={i}>
              <th scope="row" className="px-2 py-2 text-left font-normal">
                {i + 1}
              </th>
              <td className={td}>{r.matches}</td>
              <td className={td}>{pct(r.predicted)}</td>
              <td className={td}>{pct(r.observed)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SimulatorInsights() {
  const { win, chase, first_innings: first } = s;
  const test = seasonSpan(s.test);
  return (
    <div className="flex flex-col gap-6">
      <section aria-label="Headline results" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Who wins, pre-match"
          value={win.simulator.brier.toFixed(3)}
          context={`Brier score; a coin flip scores ${win.coin_flip.brier.toFixed(3)}. No better than chance.`}
        />
        <Stat
          label="Chases, from ball one"
          value={chase.simulator.brier.toFixed(3)}
          context={`Brier score; the base chase rate scores ${chase.chase_rate.brier.toFixed(3)}.`}
        />
        <Stat
          label="Totals inside 80% range"
          value={pct(first.coverage_80, 0)}
          context={`${first.matches} first innings; PIT chi-square ${first.pit_chi2} (uniform below ${first.pit_chi2_critical}).`}
        />
        <Stat
          label="10,000 matches"
          value={`${s.timing.seconds.toFixed(1)} s`}
          context="Every simulation stepped together, ball by ball, as numpy arrays."
        />
      </section>

      <Section
        id="simulator"
        title="How a match is simulated"
        lede={`Every legal ball: extras from league rates; the ball faced from the ball-outcome model; run outs at the league rate. Each over's bowler follows how that bowler was used in their last ${s.settings.history_seasons} seasons, within the four-over quota and never twice in a row. Each match draws its own conditions, shared by both innings: a spread of ${s.settings.conditions_sd}, chosen on ${seasonSpan(s.valid)} as the one whose 80% range held closest to 80% of first-innings totals.`}
      >
        <div className="overflow-x-auto" {...scrollRegion("Conditions spread tuning")}>
          <table className="w-full min-w-[24rem] text-sm">
            <caption className="sr-only">Conditions spread tuned on the validation seasons</caption>
            <thead className="border-b border-border">
              <tr className="text-xs text-muted-foreground">
                <th scope="col" className="px-2 py-2 text-left font-medium">
                  Spread
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  CRPS (runs)
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  80% range held
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {s.tuning.map((r) => (
                <tr
                  key={r.conditions_sd}
                  className={
                    r.conditions_sd === s.settings.conditions_sd
                      ? "text-foreground"
                      : "text-muted-foreground"
                  }
                >
                  <th scope="row" className="px-2 py-2 text-left font-normal">
                    {r.conditions_sd}
                    {r.conditions_sd === s.settings.conditions_sd && (
                      <span className="ml-2 font-sans text-xs text-primary">chosen</span>
                    )}
                  </th>
                  <td className="px-2 py-2 text-right">{r.crps.toFixed(2)}</td>
                  <td className="px-2 py-2 text-right">{pct(r.coverage_80)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="simulator-totals"
          title="First-innings totals"
          lede={`Every ${test} match simulated ${s.simulations_per_match.toLocaleString("en-IN")} times before a ball was bowled, with a ball model that never saw ${test}. Where each actual total fell within its simulation: a flat histogram means the spread is right. Averages: ${first.simulated_mean} simulated, ${first.actual_mean} actual.`}
        >
          <PitChart />
        </Section>
        <Section
          id="simulator-chases"
          title="From the first ball of a chase"
          lede={`With the real target, the simulated chance ranks chases well but runs low: ${pct(chase.mean_predicted)} on average against ${pct(chase.observed)} chased, most for modest targets. So the replay's what-if starts from the win probability model and adds only the simulated change.`}
        >
          <CalibrationTable rows={chase.calibration} label="Simulated chase chances by fifth" />
        </Section>
      </div>

      <Section
        id="simulator-winner"
        title="Who wins, before a ball is bowled"
        lede={`Brier score of the chance that the side batting first wins, ${test} (${s.matches} matches). Lower is better.`}
      >
        <div className="flex flex-col gap-4">
          <div
            className="overflow-x-auto"
            {...scrollRegion("Pre-match win chances against baselines")}
          >
            <table className="w-full min-w-[24rem] text-sm">
              <caption className="sr-only">Pre-match win chances against baselines</caption>
              <thead className="border-b border-border">
                <tr className="text-xs text-muted-foreground">
                  <th scope="col" className="px-2 py-2 text-left font-medium">
                    Method
                  </th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">
                    Brier
                  </th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">
                    Log loss
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono tabular-nums">
                {(
                  [
                    ["Simulator", win.simulator],
                    ["Coin flip", win.coin_flip],
                    [`Batting-first rate (${pct(win.bat_first_rate.rate)})`, win.bat_first_rate],
                    ["Both sides' recent form", win.form],
                  ] as const
                ).map(([label, m]) => (
                  <tr key={label}>
                    <th scope="row" className="px-2 py-2 text-left font-sans font-normal">
                      {label}
                    </th>
                    <td className="px-2 py-2 text-right">{m.brier.toFixed(4)}</td>
                    <td className="px-2 py-2 text-right">{m.log_loss.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            The simulator&apos;s Brier score minus a coin flip&apos;s is{" "}
            {signed(-win.gain_vs_coin_flip.value, 4)} (90%: {signed(-win.gain_vs_coin_flip.high, 4)}{" "}
            to {signed(-win.gain_vs_coin_flip.low, 4)}): no better. Before a ball is bowled, who
            wins an IPL match is close to unpredictable from XIs and form, as the{" "}
            <Link href="/lab/rivalries" className="text-primary underline-offset-4 hover:underline">
              rivalries note
            </Link>{" "}
            found too. The simulator is for distributions and what-ifs, and every page says so.
          </p>
        </div>
      </Section>
    </div>
  );
}
