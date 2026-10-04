"use client";

import { useState } from "react";
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

import { CompareLegend } from "@/components/compare/rating-comparison";
import type { PlayerProfile } from "@/lib/api/types";
import {
  type Align,
  COMPARE_SERIES,
  type CompareRole,
  type TrendPoint,
  trend,
} from "@/lib/compare";
import { signed } from "@/lib/players";
import { cn } from "@/lib/utils";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

interface TipProps {
  active?: boolean;
  payload?: readonly { payload?: TrendPoint }[];
  names: [string, string];
  align: Align;
  unit: string;
}

function Tip({ active, payload, names, align, unit }: TipProps) {
  const p = payload?.[0]?.payload;
  if (!active || !p) return null;
  const rows = [
    [names[0], p.a, p.aBalls, p.aSeason, COMPARE_SERIES.a.color],
    [names[1], p.b, p.bBalls, p.bSeason, COMPARE_SERIES.b.color],
  ] as const;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        {align === "season" ? `${p.x} season` : `Age ${p.x}`}
      </p>
      {rows.map(([name, value, balls, season, color]) => (
        <p key={name} className="flex items-center gap-2 text-muted-foreground">
          <span aria-hidden="true" className="size-2 rounded-full" style={{ background: color }} />
          {name}
          {align === "age" && season ? ` (${season})` : ""}
          <span className="ml-auto pl-3 font-mono text-foreground tabular-nums">
            {value === null ? "—" : `${signed(value, unit === "per over" ? 2 : 1)} ${unit}`}
            {value !== null && <span className="text-muted-foreground"> · {balls} balls</span>}
          </span>
        </p>
      ))}
    </div>
  );
}

/** Each season against par for both players, by season or lined up by age. */
export function TrendChart({
  a,
  b,
  role,
  names,
}: {
  a: PlayerProfile;
  b: PlayerProfile;
  role: CompareRole;
  names: [string, string];
}) {
  const ages = Boolean(a.player.date_of_birth && b.player.date_of_birth);
  const [align, setAlign] = useState<Align>("season");
  const points = trend(a, b, role, align);
  const unit = role === "batting" ? "per 100 balls" : "per over";
  const metric = role === "batting" ? "Runs above par per 100 balls" : "Runs saved per over";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <CompareLegend a={names[0]} b={names[1]} />
        {ages && (
          <div className="flex gap-1.5" role="group" aria-label="Line up by">
            {(["season", "age"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={align === value}
                onClick={() => setAlign(value)}
                className={cn(
                  "h-8 rounded-lg border px-3 text-xs transition-colors",
                  align === value
                    ? "border-primary/50 bg-primary/10 text-foreground"
                    : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {value === "season" ? "By season" : "By age"}
              </button>
            ))}
          </div>
        )}
      </div>
      {points.length ? (
        <div
          className="h-64"
          role="img"
          aria-label={`${metric} ${align === "season" ? "by season" : "by age"}: ${names[0]} in blue, ${names[1]} in orange`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="x"
                type="number"
                domain={["dataMin", "dataMax"]}
                allowDecimals={false}
                {...AXIS}
                tickLine={false}
                minTickGap={12}
              />
              <YAxis
                {...AXIS}
                tickLine={false}
                width={48}
                tickFormatter={(v: number) => v.toFixed(role === "batting" ? 0 : 1)}
              />
              <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
              <Tooltip content={<Tip names={names} align={align} unit={unit} />} />
              {(["a", "b"] as const).map((side) => (
                <Line
                  key={side}
                  dataKey={side}
                  name={names[side === "a" ? 0 : 1]}
                  stroke={COMPARE_SERIES[side].color}
                  strokeWidth={2}
                  dot={{ r: 3, strokeWidth: 0, fill: COMPARE_SERIES[side].color }}
                  activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Not enough balls in any season to plot.</p>
      )}
      <p className="text-xs leading-relaxed text-muted-foreground">
        {metric} each season; the dashed line is par, an average player on the same balls. Seasons
        under 30 balls are left out.
        {ages && " By age lines careers up on the age each player was during the season."}
      </p>
    </div>
  );
}
