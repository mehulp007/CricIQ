"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { SeasonTrend } from "@/lib/api/types";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

export const TREND_SERIES = [
  { key: "chasing_win_pct", label: "Chasing side won", color: "var(--chart-1)" },
  { key: "home_win_pct", label: "Home side won", color: "var(--chart-2)" },
  { key: "toss_winner_win_pct", label: "Toss winner won", color: "var(--chart-5)" },
] as const;

function Tip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: readonly { payload?: SeasonTrend }[];
}) {
  const p = payload?.[0]?.payload;
  if (!active || !p) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        {p.season} · {p.matches} decided matches
      </p>
      {TREND_SERIES.map((s) => {
        const value = p[s.key];
        return (
          <p key={s.key} className="flex items-center gap-2 text-muted-foreground">
            <span
              aria-hidden="true"
              className="size-2 rounded-full"
              style={{ background: s.color }}
            />
            {s.label}
            <span className="ml-auto pl-3 font-mono text-foreground tabular-nums">
              {value === null || value === undefined ? "no home games" : `${value.toFixed(1)}%`}
            </span>
          </p>
        );
      })}
    </div>
  );
}

/** Share of matches won by the chasing side, the home side and the toss winner, by season. */
export function LeagueTrendsChart({ seasons }: { seasons: SeasonTrend[] }) {
  return (
    <div className="flex flex-col gap-3">
      <ul
        className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"
        aria-label="Legend"
      >
        {TREND_SERIES.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="h-0.5 w-4 rounded-full"
              style={{ background: s.color }}
            />
            {s.label}
          </li>
        ))}
      </ul>
      <div
        className="h-64"
        role="img"
        aria-label="Share of matches won by the chasing side, the home side and the toss winner in each season, against an even 50% line"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={seasons} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="season" {...AXIS} tickLine={false} minTickGap={16} />
            <YAxis
              {...AXIS}
              tickLine={false}
              width={44}
              domain={[20, 80]}
              ticks={[20, 35, 50, 65, 80]}
              tickFormatter={(v: number) => `${v}%`}
            />
            <ReferenceLine y={50} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
            <Tooltip content={<Tip />} />
            {TREND_SERIES.map((s) => (
              <Line
                key={s.key}
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={{ r: 3, strokeWidth: 0, fill: s.color }}
                activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
