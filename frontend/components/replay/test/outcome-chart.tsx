"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DRAW_COLOR } from "@/components/replay/test/outcome-bar";
import { SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import { describeDelivery } from "@/lib/replay/engine";
import {
  dayStarts,
  inningsOffsets,
  matchOvers,
  type OutcomePoint,
  outcomeSeries,
  testTurningPoints,
} from "@/lib/replay/test";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

interface Row extends OutcomePoint {
  aPct: number;
  drawPct: number;
  bPct: number;
}

function OutcomeTooltip({
  active,
  payload,
  timeline,
}: {
  active?: boolean;
  payload?: { payload?: Row }[];
  timeline: Timeline;
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const { team_a, team_b } = timeline.summary;
  const lines = [
    [SIDE_COLORS.a, team_a.franchise_id, row.aPct],
    [DRAW_COLOR, "Draw", row.drawPct],
    [SIDE_COLORS.b, team_b.franchise_id, row.bPct],
  ] as const;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        {row.index < 0 ? row.label : `Ball ${row.label} · over ${Math.floor(row.x)} of the match`}
      </p>
      {lines.map(([color, name, value]) => (
        <p key={name} className="flex items-center gap-2 text-muted-foreground">
          <span aria-hidden="true" className="size-2 rounded-full" style={{ background: color }} />
          {name}
          <span className="ml-auto font-mono text-foreground tabular-nums">
            {value.toFixed(0)}%
          </span>
        </p>
      ))}
    </div>
  );
}

/** The three results' chances over the whole Test, with its innings and estimated days. */
export function OutcomeChart({
  timeline,
  cursor,
  onSeek,
}: {
  timeline: Timeline;
  cursor: number;
  onSeek: (index: number) => void;
}) {
  const data: Row[] = outcomeSeries(timeline, cursor).map((p) => ({
    ...p,
    aPct: p.a * 100,
    drawPct: p.draw * 100,
    bPct: p.b * 100,
  }));
  const offsets = inningsOffsets(timeline);
  const total = timeline.deliveries.length
    ? matchOvers(timeline.deliveries[timeline.deliveries.length - 1], offsets)
    : 1;
  const step = total > 300 ? 90 : 45;
  const ticks = Array.from({ length: Math.floor(total / step) + 1 }, (_, i) => i * step);
  const breaks = timeline.innings.slice(1).map((i) => ({
    innings: i.innings_no,
    x: (offsets.get(i.innings_no) ?? 0) / 6,
  }));
  const days = dayStarts(timeline)
    .filter((s) => s.day > 1 && s.index >= 0)
    .map((s) => ({ day: s.day, x: matchOvers(timeline.deliveries[s.index], offsets) }));
  const moments = testTurningPoints(timeline, 5, cursor);
  const { team_a, team_b } = timeline.summary;

  return (
    <div className="flex flex-col gap-4">
      <p className="sr-only">
        The chances of a {team_a.name} win, a draw and a {team_b.name} win after every ball, stacked
        to 100%, against the overs bowled in the match.
      </p>
      <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Legend">
        {(
          [
            [SIDE_COLORS.a, `${team_a.name} win`],
            [DRAW_COLOR, "Draw"],
            [SIDE_COLORS.b, `${team_b.name} win`],
          ] as const
        ).map(([color, label]) => (
          <li key={label} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-2 w-4 rounded-full"
              style={{ background: color }}
            />
            {label}
          </li>
        ))}
      </ul>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="x"
              type="number"
              domain={[0, Math.max(total, 1)]}
              ticks={ticks}
              {...AXIS}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(v: number) => `${v}%`}
              width={48}
              {...AXIS}
            />
            {breaks.map((b) => (
              <ReferenceLine
                key={`i${b.innings}`}
                x={b.x}
                stroke="var(--foreground)"
                strokeOpacity={0.4}
                label={{
                  value: `Inn ${b.innings}`,
                  position: "insideTopRight",
                  fill: "var(--muted-foreground)",
                  fontSize: 10,
                }}
              />
            ))}
            {days.map((d) => (
              <ReferenceLine
                key={`d${d.day}`}
                x={d.x}
                stroke="var(--border)"
                strokeDasharray="3 3"
                label={{
                  value: `Day ${d.day}`,
                  position: "insideBottomRight",
                  fill: "var(--muted-foreground)",
                  fontSize: 10,
                }}
              />
            ))}
            <Tooltip
              cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
              content={<OutcomeTooltip timeline={timeline} />}
            />
            <Area
              dataKey="aPct"
              stackId="r"
              type="linear"
              stroke="none"
              fill={SIDE_COLORS.a}
              fillOpacity={0.55}
              isAnimationActive={false}
              activeDot={false}
            />
            <Area
              dataKey="drawPct"
              stackId="r"
              type="linear"
              stroke="none"
              fill={DRAW_COLOR}
              fillOpacity={0.25}
              isAnimationActive={false}
              activeDot={false}
            />
            <Area
              dataKey="bPct"
              stackId="r"
              type="linear"
              stroke="none"
              fill={SIDE_COLORS.b}
              fillOpacity={0.55}
              isAnimationActive={false}
              activeDot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted-foreground">
        Days are estimated: Cricsheet records the dates a Test was played on, not when each day
        began, so the overs are shared evenly between them.
      </p>

      <div>
        <h3 className="text-xs tracking-wide text-muted-foreground uppercase">
          Turning points so far
        </h3>
        {moments.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            The balls that moved the match most appear here as the replay plays.
          </p>
        ) : (
          <ol className="mt-2 flex flex-col divide-y divide-border">
            {moments.map((m) => {
              const d = timeline.deliveries[m.index];
              const team = m.side === "a" ? team_a : team_b;
              return (
                <li key={m.index}>
                  <button
                    type="button"
                    onClick={() => onSeek(m.index)}
                    className="flex w-full items-start gap-3 py-2 text-left text-sm transition-colors hover:text-primary"
                  >
                    <span className="w-14 shrink-0 pt-0.5 font-mono text-xs text-muted-foreground tabular-nums">
                      {d.innings_no}·{d.ball_label}
                    </span>
                    <span className="min-w-0 flex-1 leading-snug">
                      {describeDelivery(timeline, d)}
                    </span>
                    <span className="flex shrink-0 items-center gap-1.5 font-mono text-xs tabular-nums">
                      <span
                        aria-hidden="true"
                        className="size-2 rounded-full"
                        style={{ background: SIDE_COLORS[m.side] }}
                      />
                      {team.franchise_id} +{Math.abs(m.swing).toFixed(0)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
        <p className="mt-2 text-xs text-muted-foreground">
          Points of expected result: a win counts 1 and a draw a half.
        </p>
      </div>
    </div>
  );
}
