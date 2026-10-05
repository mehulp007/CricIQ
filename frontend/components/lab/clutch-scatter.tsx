"use client";

import { useState } from "react";
import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ClutchNote } from "@/lib/lab";
import { signed } from "@/lib/lab";
import { cn } from "@/lib/utils";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

interface Point {
  name: string;
  odd: number;
  even: number;
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload?: Point }[] }) {
  const p = payload?.[0]?.payload;
  if (!active || !p) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">{p.name}</p>
      <p className="text-muted-foreground">
        Odd seasons <span className="font-mono text-foreground">{signed(p.odd)}</span>
      </p>
      <p className="text-muted-foreground">
        Even seasons <span className="font-mono text-foreground">{signed(p.even)}</span>
      </p>
    </div>
  );
}

/** Each player's clutch record in odd seasons against even seasons. */
export function ClutchScatter({ note }: { note: ClutchNote }) {
  const [role, setRole] = useState<"batting" | "bowling">("batting");
  const data = note.roles[role];
  const reach =
    Math.ceil(
      Math.max(...data.halves.flatMap((h) => [Math.abs(h.odd), Math.abs(h.even)]), 10) / 10,
    ) * 10;
  const clipped = data.halves.map((h) => ({
    name: h.name,
    odd: Math.max(-reach, Math.min(reach, h.odd)),
    even: Math.max(-reach, Math.min(reach, h.even)),
  }));
  return (
    <figure className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5" role="group" aria-label="Role">
          {(["batting", "bowling"] as const).map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={role === r}
              onClick={() => setRole(r)}
              className={cn(
                "h-8 rounded-lg border px-3 text-xs transition-colors",
                role === r
                  ? "border-primary/50 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {r === "batting" ? "Batters" : "Bowlers"}
            </button>
          ))}
        </div>
        <p className="font-mono text-xs text-muted-foreground tabular-nums">
          r = {data.split_half_r?.toFixed(2) ?? "n/a"} · {data.players} players
        </p>
      </div>
      <div
        className="h-72"
        role="img"
        aria-label={`Clutch record of ${data.players} ${role === "batting" ? "batters" : "bowlers"} in odd seasons against even seasons; correlation ${data.split_half_r?.toFixed(2) ?? "not available"}.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: -8 }}>
            <CartesianGrid stroke="var(--border)" />
            <XAxis
              type="number"
              dataKey="odd"
              domain={[-reach, reach]}
              name="Odd seasons"
              {...AXIS}
              label={{
                value: "Odd seasons",
                position: "insideBottom",
                offset: -10,
                fill: "var(--muted-foreground)",
                fontSize: 11,
              }}
            />
            <YAxis
              type="number"
              dataKey="even"
              domain={[-reach, reach]}
              name="Even seasons"
              width={48}
              {...AXIS}
            />
            <ReferenceLine x={0} stroke="var(--muted-foreground)" strokeDasharray="4 3" />
            <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeDasharray="4 3" />
            <Tooltip content={<Tip />} cursor={false} />
            <Scatter
              data={clipped}
              fill="var(--chart-3)"
              fillOpacity={0.7}
              isAnimationActive={false}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="text-xs leading-relaxed text-muted-foreground">
        Runs above expectation per 100 balls in high-pressure balls minus the rest
        {role === "bowling" ? " (runs saved, for bowlers)" : ""}, for players with{" "}
        {data.min_high_balls}+ high-pressure balls in both halves. A real skill would line the
        points up from bottom left to top right. Shuffling the halves at random gives correlations
        within ±{data.null_90?.toFixed(2) ?? "n/a"} nine times in ten.
      </figcaption>
    </figure>
  );
}
