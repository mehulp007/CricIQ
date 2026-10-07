"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import { describeDelivery } from "@/lib/replay/engine";
import {
  inningsOvers,
  overTicks,
  turningPoints,
  type WpPoint,
  wpSeries,
} from "@/lib/replay/win-probability";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

interface ChartRow extends WpPoint {
  above: number;
  below: number;
}

function WpTooltip({
  active,
  payload,
  timeline,
  overs,
}: {
  active?: boolean;
  payload?: { payload?: ChartRow }[];
  timeline: Timeline;
  overs: number;
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const { team_a, team_b } = timeline.summary;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        {row.index < 0 ? row.label : `Ball ${row.label}${row.x > overs ? " (chase)" : ""}`}
      </p>
      {(
        [
          ["a", team_a.franchise_id, row.wp],
          ["b", team_b.franchise_id, 100 - row.wp],
        ] as const
      ).map(([side, name, value]) => (
        <p key={side} className="flex items-center gap-2 text-muted-foreground">
          <span
            aria-hidden="true"
            className="size-2 rounded-full"
            style={{ background: SIDE_COLORS[side] }}
          />
          {name}
          <span className="ml-auto font-mono text-foreground tabular-nums">
            {value.toFixed(0)}%
          </span>
        </p>
      ))}
    </div>
  );
}

export function WinProbabilityChart({
  timeline,
  cursor,
  onSeek,
}: {
  timeline: Timeline;
  cursor: number;
  onSeek: (index: number) => void;
}) {
  const overs = inningsOvers(timeline);
  const data: ChartRow[] = wpSeries(timeline, cursor).map((p) => ({
    ...p,
    above: Math.max(p.wp, 50),
    below: Math.min(p.wp, 50),
  }));
  const moments = turningPoints(timeline, 5, cursor);
  const { team_a, team_b } = timeline.summary;

  return (
    <div className="flex flex-col gap-4">
      <p className="sr-only">
        Win probability of {team_a.name} after every ball. Above 50% {team_a.name} are ahead, below
        50% {team_b.name} are ahead.
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
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(v: number) => `${v}%`}
              width={48}
              {...AXIS}
            />
            <ReferenceLine y={50} stroke="var(--muted-foreground)" strokeDasharray="4 3" />
            <ReferenceLine
              x={overs}
              stroke="var(--border)"
              label={{
                value: "Chase",
                position: "insideTopRight",
                fill: "var(--muted-foreground)",
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
              content={<WpTooltip timeline={timeline} overs={overs} />}
            />
            <Area
              dataKey="above"
              baseValue={50}
              type="linear"
              stroke="none"
              fill={SIDE_COLORS.a}
              fillOpacity={0.25}
              isAnimationActive={false}
              activeDot={false}
            />
            <Area
              dataKey="below"
              baseValue={50}
              type="linear"
              stroke="none"
              fill={SIDE_COLORS.b}
              fillOpacity={0.25}
              isAnimationActive={false}
              activeDot={false}
            />
            <Line
              dataKey="wp"
              type="linear"
              stroke="var(--foreground)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--card)" }}
              isAnimationActive={false}
            />
            {moments.map((m) => {
              const point = data.find((p) => p.index === m.index);
              return point ? (
                <ReferenceDot
                  key={m.index}
                  x={point.x}
                  y={point.wp}
                  r={5}
                  fill={SIDE_COLORS[m.side]}
                  stroke="var(--card)"
                  strokeWidth={2}
                />
              ) : null;
            })}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h3 className="text-xs tracking-wide text-muted-foreground uppercase">
          Turning points so far
        </h3>
        {moments.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            The biggest swings appear here as the replay plays.
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
                    <span className="w-9 shrink-0 pt-0.5 font-mono text-xs text-muted-foreground tabular-nums">
                      {d.ball_label}
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
                      {team.franchise_id} +{Math.abs(m.swing).toFixed(0)}%
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
