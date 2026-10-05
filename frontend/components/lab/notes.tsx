import Link from "next/link";
import type { ReactNode } from "react";

import { ClutchScatter } from "@/components/lab/clutch-scatter";
import { IntervalRows } from "@/components/lab/interval-rows";
import { Panel } from "@/components/players/profile-parts";
import { scrollRegion } from "@/lib/a11y";
import {
  CLUTCH,
  type ClutchRole,
  MOMENTUM,
  PRESSURE,
  RIVALRIES,
  type RivalryGroup,
  signed,
} from "@/lib/lab";
import { cn } from "@/lib/utils";

function Prose({ children }: { children: ReactNode }) {
  return (
    <div className="flex max-w-3xl flex-col gap-3 leading-relaxed text-muted-foreground">
      {children}
    </div>
  );
}

function Strong({ children }: { children: ReactNode }) {
  return <span className="font-medium text-foreground">{children}</span>;
}

function Finding({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card/70 p-5">
      <p className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-2 font-mono text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{detail}</p>
    </div>
  );
}

function interval(e: { value: number; low: number; high: number }, digits: number): string {
  return `${signed(e.value, digits)} (90%: ${signed(e.low, digits)} to ${signed(e.high, digits)})`;
}

const EXPECTED = (
  <>
    &quot;Expected&quot; comes from the{" "}
    <Link href="/models" className="text-foreground underline-offset-4 hover:underline">
      ball-outcome model
    </Link>
    , which already knows the batter, the bowler, the phase, the wickets down, how settled the
    batter is and the chase equation.
  </>
);

// --------------------------------------------------------------------------- momentum

export function MomentumNoteView() {
  const m = MOMENTUM;
  const hot = m.bands[m.bands.length - 1];
  const cold = m.bands[0];
  return (
    <div className="flex flex-col gap-8">
      <Prose>
        <p>
          <Strong>Momentum</Strong> in CricIQ is the change in the batting side&apos;s win
          probability over the last 12 legal balls, in percentage points. It is shown in every
          replay. Commentators treat momentum as a force; the test is whether it carries forward.
          From the end of every over with at least 12 balls on either side (
          {m.states.toLocaleString("en-IN")} moments in {m.matches.toLocaleString("en-IN")}{" "}
          matches), we compare momentum with what happened next.
        </p>
        <p>{EXPECTED} Intervals come from resampling whole matches.</p>
      </Prose>

      <div className="grid gap-4 sm:grid-cols-3">
        <Finding
          label="Next 12 balls, per 10 points"
          value={`${signed(m.runs_per_10_points.value, 2)} runs`}
          detail={`Above expectation. 90% interval ${signed(m.runs_per_10_points.low, 2)} to ${signed(m.runs_per_10_points.high, 2)}: real, but small.`}
        />
        <Finding
          label="Wickets, per 10 points"
          value={signed(m.wickets_per_10_points.value, 3)}
          detail="Above expectation: sides on a run also lose slightly more wickets. They are attacking, not suddenly better."
        />
        <Finding
          label="Result, per 10 points"
          value={`${signed(100 * m.result_per_10_points.value, 2)} pts`}
          detail="Win rate minus win probability. Momentum adds nothing to the model's estimate; if anything the model slightly overrates a hot streak."
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          id="momentum-runs"
          title="The next two overs"
          lede="Runs above expectation in the next 12 balls faced, by momentum over the previous 12."
        >
          <IntervalRows
            rows={m.bands.map((b) => ({
              label: b.label,
              detail: `${b.states.toLocaleString("en-IN")} moments · ${b.runs_next_12.toFixed(1)} runs`,
              estimate: b.runs_above_expected,
            }))}
            unit="runs"
            digits={2}
            caption={`A 15-point surge is followed by ${signed(hot.runs_above_expected.value, 1)} runs above expectation; a 15-point slump by ${signed(cold.runs_above_expected.value, 1)}. Twelve balls usually bring about 16 runs.`}
          />
        </Panel>
        <Panel
          id="momentum-result"
          title="The result"
          lede="How often the batting side won, minus its win probability at the moment, in points."
        >
          <IntervalRows
            rows={m.bands.map((b) => ({
              label: b.label,
              estimate: {
                value: 100 * b.result_above_wp.value,
                low: 100 * b.result_above_wp.low,
                high: 100 * b.result_above_wp.high,
              },
            }))}
            unit="points"
            color="var(--chart-4)"
            caption="Near zero: the win probability already prices in the last two overs (its features include them). After the biggest surges the batting side wins slightly less often than the model says, so if anything it overreacts."
          />
        </Panel>
      </div>

      <Panel id="momentum-verdict" title="Verdict">
        <Prose>
          <p>
            Momentum is <Strong>descriptive, not predictive</Strong>. It is a useful summary of
            which way a match has been going, so the replay shows it, but it should not change an
            estimate: a side that has just surged is barely more likely to keep scoring, and no more
            likely to win, than the situation already says. Slope per 10 points:{" "}
            {interval(m.runs_per_10_points, 2)} runs over the next 12 balls.
          </p>
          <p>
            Limits: twelve balls is one choice of window; momentum is measured with CricIQ&apos;s
            own win probability model, and the test uses the served models, which were fitted on
            these seasons.
          </p>
        </Prose>
      </Panel>
    </div>
  );
}

// --------------------------------------------------------------------------- pressure

export function PressureNoteView() {
  const p = PRESSURE;
  const chase = p.rows.filter((r) => r.innings_no === 2);
  const first = p.rows.filter((r) => r.innings_no === 1);
  const extreme = chase.find((r) => r.band === "Very high");
  return (
    <div className="flex flex-col gap-8">
      <Prose>
        <p>
          Before every ball, CricIQ asks how much that ball can move the match. It tries each
          possible outcome (a dot, 1, 2, 3, 4, 6, a wicket, a wide), scores the resulting state with
          the win probability model, and weights the swings by how often each outcome happens in
          that situation. That expected swing, divided by the average for every IPL ball, is the{" "}
          <Strong>leverage</Strong> (the Leverage Index from baseball analytics); its percentile
          among every ball since 2008 is the <Strong>pressure index</Strong> shown in the replay:
          Low below 50, Medium to 80, High to 95, Very high above.
        </p>
        <p>
          {EXPECTED} So the comparison asks whether batters do something different under pressure
          beyond what the situation itself implies. Based on {p.balls.toLocaleString("en-IN")} balls
          faced.
        </p>
      </Prose>

      {extreme && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Finding
            label="Very high pressure, chasing"
            value={`${extreme.strike_rate.toFixed(0)} vs ${extreme.expected_strike_rate.toFixed(0)}`}
            detail="Strike rate against expectation: batters swing harder than even the chase equation implies."
          />
          <Finding
            label="Dismissals per 100 balls"
            value={`${extreme.dismissals_per_100.toFixed(1)} vs ${extreme.expected_dismissals_per_100.toFixed(1)}`}
            detail="And they get out more: the extra runs are bought with risk."
          />
          <Finding
            label="Share of chase balls"
            value={`${(100 * extreme.share).toFixed(0)}%`}
            detail="Very high pressure is rare in the first innings and common at the end of close chases."
          />
        </div>
      )}

      <Panel
        id="pressure-check"
        title="Does leverage work?"
        lede="Every ball since 2008 grouped into tenths by leverage: the swing the model expected against the swing that actually happened on the next ball, both relative to a typical ball."
      >
        <div className="overflow-x-auto" {...scrollRegion("Expected and realised swings")}>
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-2 py-2 text-left font-medium">
                  Tenth
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Expected
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Happened
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  90% interval
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {p.swing_check.map((r, i) => (
                <tr key={i}>
                  <th scope="row" className="px-2 py-2 text-left font-sans font-normal">
                    {i === 0 ? "Calmest" : i === p.swing_check.length - 1 ? "Tensest" : i + 1}
                  </th>
                  <td className="px-2 py-2 text-right">{r.leverage.toFixed(2)}×</td>
                  <td className="px-2 py-2 text-right font-semibold">
                    {r.realised.value.toFixed(2)}×
                  </td>
                  <td className="px-2 py-2 text-right text-muted-foreground">
                    {r.realised.low.toFixed(2)} to {r.realised.high.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          The two columns agree all the way from the calmest balls to the tensest: when CricIQ says
          a ball matters three times as much as usual, the win probability really does move about
          three times as far.
        </p>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        {[
          ["pressure-chase", "Chasing", chase],
          ["pressure-first", "Batting first", first],
        ].map(([id, title, rows]) => (
          <Panel
            key={id as string}
            id={id as string}
            title={title as string}
            lede="Runs per 100 balls above expectation, by pressure band."
          >
            <IntervalRows
              rows={(rows as typeof chase).map((r) => ({
                label: `${r.band} pressure`,
                detail: `${r.share < 0.01 ? "<1" : (100 * r.share).toFixed(0)}% of balls · SR ${r.strike_rate.toFixed(0)} vs ${r.expected_strike_rate.toFixed(0)} expected`,
                estimate: r.runs_above_expected_per_100,
              }))}
              unit="runs per 100 balls"
              caption="Intervals crossing the line mean no detectable difference from expectation."
            />
          </Panel>
        ))}
      </div>

      <Panel
        id="pressure-table"
        title="The full picture"
        lede="Each band against what the ball-outcome model expected of the same batters, bowlers and situations."
      >
        <div className="overflow-x-auto" {...scrollRegion("Batting by pressure band")}>
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                {[
                  "Pressure",
                  "Innings",
                  "Balls",
                  "SR",
                  "Expected",
                  "Dot %",
                  "4s & 6s %",
                  "Out /100",
                  "Expected",
                ].map((h, i) => (
                  <th
                    key={`${h}-${i}`}
                    scope="col"
                    className={cn("px-2 py-2 font-medium", i < 2 ? "text-left" : "text-right")}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {p.rows.map((r) => (
                <tr key={`${r.band}-${r.innings_no}`}>
                  <th scope="row" className="px-2 py-2 text-left font-sans font-normal">
                    {r.band}
                  </th>
                  <td className="px-2 py-2 font-sans text-muted-foreground">
                    {r.innings_no === 1 ? "First" : "Chase"}
                  </td>
                  <td className="px-2 py-2 text-right text-muted-foreground">
                    {r.balls.toLocaleString("en-IN")}
                  </td>
                  <td className="px-2 py-2 text-right font-semibold">{r.strike_rate.toFixed(1)}</td>
                  <td className="px-2 py-2 text-right text-muted-foreground">
                    {r.expected_strike_rate.toFixed(1)}
                  </td>
                  <td className="px-2 py-2 text-right">{r.dot_pct.toFixed(1)}</td>
                  <td className="px-2 py-2 text-right">{r.boundary_pct.toFixed(1)}</td>
                  <td className="px-2 py-2 text-right">{r.dismissals_per_100.toFixed(2)}</td>
                  <td className="px-2 py-2 text-right text-muted-foreground">
                    {r.expected_dismissals_per_100.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        id="pressure-moments"
        title="The highest-pressure balls in IPL history"
        lede="One per match. Leverage is how many typical balls this one was worth. Open a replay to see it unfold."
      >
        <ol className="flex flex-col divide-y divide-border">
          {p.top_moments.map((m) => (
            <li key={m.match_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
              <span className="w-14 font-mono text-sm font-semibold tabular-nums">
                {m.leverage.toFixed(0)}×
              </span>
              <span className="min-w-0 flex-1 text-sm">
                <span className="font-medium">{m.situation}</span>
                <span className="text-muted-foreground">
                  {" "}
                  · {m.teams}, {m.season}
                  {m.stage !== "League" ? ` ${m.stage.toLowerCase()}` : ""} · {m.bowler} to bowl:{" "}
                  {m.happened}. {m.result}.
                </span>
              </span>
              <Link
                href={`/matches/${m.match_id}?ball=${m.innings_no}.${m.seq_no}`}
                className="text-xs text-primary underline-offset-4 hover:underline"
              >
                Replay
              </Link>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel id="pressure-verdict" title="Verdict">
        <Prose>
          <p>
            Pressure changes behaviour at the very end of close chases: batters attack more than the
            required rate alone would explain, and pay for it with wickets. In ordinary pressure the
            differences are within a run or two per 100 balls.
          </p>
          <p>
            Limits: leverage inherits the win probability model&apos;s view of each state; outcome
            chances come from the league&apos;s rates by innings, phase and wickets in hand, not
            from the players at the crease; and pressure here is the match situation, not what
            players feel.
          </p>
        </Prose>
      </Panel>
    </div>
  );
}

// --------------------------------------------------------------------------- clutch

function verdict(role: ClutchRole): string {
  const r = role.split_half_r;
  if (r === null) return "too few players to tell";
  if (r >= role.reliable_r) return "a skill that persists";
  if (role.null_90 !== null && Math.abs(r) <= role.null_90) return "no detectable skill";
  return `at most a faint signal, far below the ${role.reliable_r} a rating would need`;
}

export function ClutchNoteView() {
  const c = CLUTCH;
  const bat = c.roles.batting;
  const bowl = c.roles.bowling;
  return (
    <div className="flex flex-col gap-8">
      <Prose>
        <p>
          A player&apos;s <Strong>clutch record</Strong> here is their runs above expectation per
          100 balls in high-pressure balls (pressure index {c.high_pressure} or more) minus the same
          in every other ball; for bowlers, runs saved. {EXPECTED} If clutch were a skill, players
          good under pressure in some seasons would be good under pressure in others. So we split
          every career into odd and even seasons and compare.
        </p>
      </Prose>

      <div className="grid gap-4 sm:grid-cols-2">
        <Finding
          label="Batters, odd vs even seasons"
          value={`r = ${bat.split_half_r?.toFixed(2) ?? "n/a"}`}
          detail={`${bat.players} batters. Shuffled at random, the halves give correlations within ±${bat.null_90?.toFixed(2) ?? "n/a"} nine times in ten (p = ${bat.p_value?.toFixed(2) ?? "n/a"}): ${verdict(bat)}.`}
        />
        <Finding
          label="Bowlers, odd vs even seasons"
          value={`r = ${bowl.split_half_r?.toFixed(2) ?? "n/a"}`}
          detail={`${bowl.players} bowlers, against ±${bowl.null_90?.toFixed(2) ?? "n/a"} by chance (p = ${bowl.p_value?.toFixed(2) ?? "n/a"}): ${verdict(bowl)}.`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          id="clutch-halves"
          title="Under pressure, season to season"
          lede="Each point is a player: clutch record in odd seasons (across) against even seasons (up)."
        >
          <ClutchScatter note={c} />
        </Panel>
        <Panel
          id="clutch-careers"
          title="The most-tested batters"
          lede="Career clutch records of the batters with the most high-pressure balls, with 90% intervals."
        >
          <IntervalRows
            rows={bat.most_exposed.slice(0, 10).map((p) => ({
              label: p.name,
              detail: `${p.high_balls.toLocaleString("en-IN")} high-pressure balls`,
              estimate: { value: p.clutch, low: p.low, high: p.high },
            }))}
            unit="runs per 100 balls"
            caption="Even with a thousand high-pressure balls, the intervals span about 20 runs per 100 balls and almost all include zero."
          />
        </Panel>
      </div>

      <Panel id="clutch-verdict" title="Verdict">
        <Prose>
          <p>
            Clutch is <Strong>not a reliable skill</Strong> in IPL data, so CricIQ does not rate it.
            For batters there may be a faint tilt that persists, but it is far too weak to rank
            anyone: a high-pressure record mostly reflects which moments a player happened to face
            and how they went. Pressure still matters to the match (see{" "}
            <Link
              href="/lab/pressure"
              className="text-foreground underline-offset-4 hover:underline"
            >
              what pressure does to batting
            </Link>
            ); what does not persist is one player handling it better than their overall record
            says.
          </p>
          <p>
            Limits: a career split into halves has fewer high-pressure balls than a full career, so
            a very small skill could hide in the noise; the comparison is with each player&apos;s
            own expected output, which already includes their overall ability.
          </p>
        </Prose>
      </Panel>
    </div>
  );
}

// --------------------------------------------------------------------------- rivalries

function excessRows(groups: RivalryGroup[], detail: (g: RivalryGroup) => string) {
  return groups
    .filter((g) => g.excess)
    .map((g) => ({ label: g.label, detail: detail(g), estimate: g.excess! }));
}

export function RivalriesNoteView() {
  const r = RIVALRIES;
  const lead = r.rivalry[0];
  const p = r.persistence;
  const best = r.form_scan.reduce((a, b) => (b.log_loss < a.log_loss ? b : a));
  return (
    <div className="flex flex-col gap-8">
      <Prose>
        <p>
          To ask whether a rivalry or a knack for tight finishes predicts anything, we first need an
          expectation that knows nothing about either. Here it is each side&apos;s{" "}
          <Strong>form</Strong>: its results in its previous 14 matches, from before the match only,
          combined into a win chance with the log5 formula. Then we check whether{" "}
          {r.meetings.toLocaleString("en-IN")} IPL matches since 2008 beat that expectation in the
          ways a rivalry or a clutch team would.
        </p>
      </Prose>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Finding
          label="Side in better form won"
          value={`${r.favourite.win_pct ?? "n/a"}%`}
          detail={`Expected ${r.favourite.expected_pct ?? "n/a"}%. Recent results say little about the next match.`}
        />
        <Finding
          label="A season's win rate, next season"
          value={`r = ${p.win_r?.toFixed(2) ?? "n/a"}`}
          detail={`Across ${p.season_pairs} pairs of consecutive seasons: last year's table barely predicts this year's.`}
        />
        <Finding
          label={`Rivalry leaders (${lead ? lead.label.replace("Won ", "won ") : ""})`}
          value={lead?.excess ? `${signed(lead.excess.value, 1)} pts` : "n/a"}
          detail={
            lead?.excess
              ? `Win rate above form, 90%: ${signed(lead.excess.low, 1)} to ${signed(lead.excess.high, 1)}. No hold.`
              : "Too few meetings."
          }
        />
        <Finding
          label="Close finishes, next season"
          value={`r = ${p.close_r?.toFixed(2) ?? "n/a"}`}
          detail={`${p.pairs} team-seasons; chance alone gives ±${p.null_90?.toFixed(2) ?? "n/a"} nine times in ten (p = ${p.p_value?.toFixed(2) ?? "n/a"}).`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          id="rivalries-form"
          title="How much form is worth"
          lede={`Form is pulled toward an even record as if each side had also played ${r.form_prior} matches at 50%: the strength that predicts results best. Less pull makes the predictions worse than a coin flip.`}
        >
          <div className="overflow-x-auto" {...scrollRegion("Prediction error by shrinkage")}>
            <table className="w-full min-w-[20rem] text-sm">
              <thead className="border-b border-border">
                <tr className="text-xs text-muted-foreground">
                  <th scope="col" className="px-2 py-2 text-left font-medium">
                    Pull toward even (matches at 50%)
                  </th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">
                    Log loss
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono tabular-nums">
                {r.form_scan.map((f) => (
                  <tr key={f.prior} className={cn(f.prior === best.prior && "text-foreground")}>
                    <th scope="row" className="px-2 py-2 text-left font-normal">
                      {f.prior}
                      {f.prior === best.prior && (
                        <span className="ml-2 text-xs text-primary">best</span>
                      )}
                    </th>
                    <td className="px-2 py-2 text-right">{f.log_loss.toFixed(4)}</td>
                  </tr>
                ))}
                <tr className="text-muted-foreground">
                  <th scope="row" className="px-2 py-2 text-left font-normal">
                    Coin flip
                  </th>
                  <td className="px-2 py-2 text-right">{r.coin_flip_log_loss.toFixed(4)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="mt-6">
            <IntervalRows
              rows={excessRows(
                r.calibration,
                (g) => `${g.meetings} matches · won ${g.win_pct}%, expected ${g.expected_pct}%`,
              )}
              unit="points of win rate above form"
              caption="The favourite's win rate minus its expected rate, by how strongly form favoured it. Intervals that cross zero mean the expectation holds."
            />
          </div>
        </Panel>

        <Panel
          id="rivalries-hold"
          title="Do rivalry leaders keep winning?"
          lede={`Matches where the two sides had met at least ${r.min_prior} times before, seen from the side that had won more of those meetings.`}
        >
          <IntervalRows
            rows={excessRows(
              r.rivalry,
              (g) => `${g.meetings} matches · won ${g.win_pct}%, expected ${g.expected_pct}%`,
            )}
            unit="points of win rate above form"
            caption={
              r.edge_per_10
                ? `Each extra 10 points of past dominance comes with ${interval(r.edge_per_10, 1)} points of win rate above form in the next meeting: indistinguishable from nothing.`
                : "Too few meetings to measure."
            }
          />
        </Panel>
      </div>

      <Panel
        id="rivalries-close"
        title="Close finishes"
        lede={`${r.close_share}% of matches end within 5 runs, with 2 balls or fewer to spare, or in a super over.`}
      >
        <div className="grid gap-6 xl:grid-cols-2">
          <IntervalRows
            rows={excessRows(
              r.favourites,
              (g) =>
                `${g.meetings} matches · favourite won ${g.win_pct}%, expected ${g.expected_pct}%`,
            )}
            unit="points of win rate above form"
            caption="The side in better form wins close finishes about as often as any other match: no sign that better sides close them out."
          />
          <Prose>
            <p>
              If some sides had a knack for tight finishes, their close-finish record would carry
              over from one season to the next. Across {p.pairs} pairs of consecutive seasons with
              at least {p.min_close} close finishes in both, it carries over with a correlation of{" "}
              <Strong>{p.close_r?.toFixed(2) ?? "n/a"}</Strong>, inside the ±
              {p.null_90?.toFixed(2) ?? "n/a"} that shuffled seasons give nine times in ten. But a
              side&apos;s whole record carries over barely more (r = {p.win_r?.toFixed(2) ?? "n/a"}
              ), so this test can rule out a large effect, not a small one.
            </p>
          </Prose>
        </div>
      </Panel>

      <Panel id="rivalries-verdict" title="Verdict">
        <Prose>
          <p>
            Head-to-head records describe the past and <Strong>predict nothing</Strong> beyond form.
            A franchise&apos;s squad turns over every few seasons through the auction, so a rivalry
            is between badges more than teams. Close finishes behave like coin flips, and even form
            is a weak guide, which is why the Teams pages set every head-to-head record against form
            and the range chance allows.
          </p>
          <p>
            Limits: form here is results only, not the players available; the shrinkage was chosen
            on these same matches (one number, so little room to overfit); a real but small rivalry
            or close-finish effect could hide inside the intervals.
          </p>
        </Prose>
      </Panel>
    </div>
  );
}
