"use client";

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Timeline } from "@/lib/api/types";
import {
  PRESSURE_BANDS,
  type PressurePoint,
  formatLeverage,
  pressureBand,
  pressurePeaks,
  pressureSeries,
} from "@/lib/replay/pressure";
import { inningsOvers, overTicks } from "@/lib/replay/win-probability";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };
const COLOR = "var(--chart-4)";
const FLOOR = 0.25;
const CEILING = 32;
const TICKS = [0.25, 0.5, 1, 2, 4, 8, 16, 32];

function PressureTooltip({
  active,
  payload,
  overs,
}: {
  active?: boolean;
  payload?: { payload?: PressurePoint }[];
  overs: number;
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        {row.index < 0
          ? "Before the first ball"
          : `After ball ${row.label}${row.x > overs ? " (chase)" : ""}`}
      </p>
      <p className="text-muted-foreground">
        {pressureBand(row.pressure)} pressure{" "}
        <span className="font-mono text-foreground tabular-nums">{row.pressure}/100</span>
      </p>
      <p className="text-muted-foreground">
        Next ball matters{" "}
        <span className="font-mono text-foreground tabular-nums">
          {formatLeverage(row.leverage)}
        </span>{" "}
        a typical one
      </p>
    </div>
  );
}

/** Leverage of the next ball after every delivery (log scale), with the peaks so far. */
export function PressureChart({
  timeline,
  cursor,
  onSeek,
}: {
  timeline: Timeline;
  cursor: number;
  onSeek: (index: number) => void;
}) {
  const overs = inningsOvers(timeline);
  const data = pressureSeries(timeline, cursor).map((p) => ({
    ...p,
    plotted: Math.min(Math.max(p.leverage, FLOOR), CEILING),
  }));
  const peaks = pressurePeaks(timeline, cursor);
  const thresholds = timeline.win_probability?.pressure_thresholds ?? [];
  return (
    <div className="flex flex-col gap-4">
      <p className="sr-only">
        How much the next ball can move the win probability after every delivery, as a multiple of a
        typical ball in the competition, on a log scale. Dashed lines mark where medium, high and
        very high pressure begin.
      </p>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="x"
              type="number"
              domain={[0, 2 * overs]}
              ticks={overTicks(2 * overs, overs)}
              tickFormatter={(v: number) => String(v <= overs ? v : v - overs)}
              {...AXIS}
            />
            <YAxis
              scale="log"
              domain={[FLOOR, CEILING]}
              ticks={TICKS}
              allowDataOverflow
              tickFormatter={(v: number) => `${v}×`}
              width={48}
              {...AXIS}
            />
            {PRESSURE_BANDS.slice(1, thresholds.length + 1).map((b, i) => (
              <ReferenceLine
                key={b.label}
                y={thresholds[i]}
                stroke="var(--muted-foreground)"
                strokeOpacity={0.5}
                strokeDasharray="4 3"
              />
            ))}
            <ReferenceLine x={overs} stroke="var(--border)" />
            <Tooltip
              cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
              content={<PressureTooltip overs={overs} />}
            />
            <Line
              dataKey="plotted"
              type="linear"
              stroke={COLOR}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--card)" }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {thresholds.length > 0 && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          How much the next ball can move the match, as a multiple of a typical ball. Dashed lines
          mark where pressure turns{" "}
          {PRESSURE_BANDS.slice(1, thresholds.length + 1)
            .map((b, i) => `${b.label.toLowerCase()} (${formatLeverage(thresholds[i])})`)
            .join(", ")}
          .
        </p>
      )}

      <div>
        <h3 className="text-xs tracking-wide text-muted-foreground uppercase">
          Highest pressure so far
        </h3>
        {peaks.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            The tensest moments appear here as the replay plays.
          </p>
        ) : (
          <ol className="mt-2 flex flex-col divide-y divide-border">
            {peaks.map((p) => {
              const d = timeline.deliveries[p.index];
              const inn = timeline.innings.find((i) => i.innings_no === d.innings_no);
              const situation =
                d.innings_no === 2 && inn?.target_runs
                  ? `${inn.target_runs - d.team_runs} needed from ${(inn.max_balls ?? 0) - d.legal_ball_no}`
                  : `${d.team_runs}/${d.team_wickets}`;
              return (
                <li key={p.index}>
                  <button
                    type="button"
                    onClick={() => onSeek(p.index)}
                    className="flex w-full items-center gap-3 py-2 text-left text-sm transition-colors hover:text-primary"
                  >
                    <span className="w-9 shrink-0 font-mono text-xs text-muted-foreground tabular-nums">
                      {d.ball_label}
                    </span>
                    <span className="min-w-0 flex-1">{situation}</span>
                    <span className="shrink-0 font-mono text-xs tabular-nums">
                      {formatLeverage(p.leverage)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
