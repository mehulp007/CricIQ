import { SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import { describeFactor, explanationAt, formatPercent, wpAt } from "@/lib/replay/win-probability";

function formatPoints(points: number): string {
  const rounded = Math.round(points);
  if (rounded === 0) return "±0";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)}`;
}

/**
 * Why the model says what it says: each factor's push, in percentage points,
 * toward the batting side (right) or the fielding side (left).
 */
export function ExplainPanel({ timeline, cursor }: { timeline: Timeline; cursor: number }) {
  if (!timeline.win_probability) return null;
  const explanation = explanationAt(timeline, cursor);
  const wp = wpAt(timeline, cursor);

  if (!explanation || wp === null) {
    return (
      <section
        aria-label="Why this estimate"
        className="rounded-2xl border border-border bg-card/70 p-5"
      >
        <h2 className="text-xs tracking-wide text-muted-foreground uppercase">Why this estimate</h2>
        <p className="mt-3 text-sm text-muted-foreground">
          {cursor >= 0 && timeline.deliveries[cursor]?.innings_no > 2
            ? "Super overs are not modelled. The estimate holds where regulation play ended."
            : "The result is settled, so there is nothing left to estimate."}
        </p>
      </section>
    );
  }

  const { summary } = timeline;
  // Models that use the sides' and batters' records (the "teams" factor), e.g. the T20Is'.
  const usesTeams = timeline.win_probability.factor_keys.includes("teams");
  if (cursor < 0) {
    return (
      <section
        aria-label="Why this estimate"
        className="rounded-2xl border border-border bg-card/70 p-5"
      >
        <h2 className="text-xs tracking-wide text-muted-foreground uppercase">Why this estimate</h2>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Before a ball is bowled, the model gives the side batting first{" "}
          <span className="font-mono font-semibold text-foreground tabular-nums">
            {formatPercent(wp)}
          </span>
          {usesTeams
            ? ", from how often sides batting first win in this era, adjusted for the two squads' records and the opening batters' records. From the first ball, the score, wickets and balls left take over."
            : ", close to how often sides batting first win in this era. Team and player records are not used: in testing they did not improve the estimates. From the first ball, the score, wickets and balls left take over."}
        </p>
      </section>
    );
  }

  const batting = explanation.battingSide === "a" ? summary.team_a : summary.team_b;
  const fielding = explanation.battingSide === "a" ? summary.team_b : summary.team_a;
  const battingWp = explanation.battingSide === "a" ? wp : 1 - wp;
  const scale = Math.max(10, ...explanation.factors.map((f) => Math.abs(f.points)));
  const moment = explanation.inningsNo === 1 ? "first-innings moment" : "moment in a chase";

  return (
    <section
      aria-label="Why this estimate"
      className="rounded-2xl border border-border bg-card/70 p-5"
    >
      <h2 className="text-xs tracking-wide text-muted-foreground uppercase">Why this estimate</h2>
      <p className="mt-2 text-sm">
        <span className="font-medium">{batting.name}</span>{" "}
        <span className="font-mono font-semibold tabular-nums">{formatPercent(battingWp)}</span>
        <span className="text-muted-foreground">
          {" "}
          vs {formatPercent(explanation.base)} for an average {moment}
        </span>
      </p>

      <ul className="mt-4 flex flex-col gap-3.5">
        {explanation.factors.map((factor) => {
          const text = describeFactor(timeline, cursor, factor.key);
          const helps = factor.points >= 0;
          const width = (Math.abs(factor.points) / scale) * 50;
          return (
            <li key={factor.key} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>
                  {text.label}
                  <span className="ml-2 text-xs text-muted-foreground">{text.detail}</span>
                </span>
                <span className="shrink-0 font-mono text-xs tabular-nums">
                  {formatPoints(factor.points)} pts
                </span>
              </div>
              <div className="relative h-1.5 rounded-full bg-muted" aria-hidden="true">
                <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
                <span
                  className="absolute inset-y-0 rounded-full transition-all duration-500 ease-out"
                  style={{
                    background: helps
                      ? SIDE_COLORS[explanation.battingSide]
                      : SIDE_COLORS[explanation.battingSide === "a" ? "b" : "a"],
                    width: `${width}%`,
                    left: helps ? "50%" : `${50 - width}%`,
                  }}
                />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 flex justify-between text-[11px] text-muted-foreground">
        <span>Helps {fielding.franchise_id}</span>
        <span>Helps {batting.franchise_id}</span>
      </p>
    </section>
  );
}
