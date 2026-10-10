"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import { inningsLabel } from "@/lib/format";
import { oversUpTo } from "@/lib/replay/engine";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

/** Runs per over in the innings being played, up to the cursor. */
export function InningsOvers({ timeline, cursor }: { timeline: Timeline; cursor: number }) {
  const d = cursor >= 0 ? timeline.deliveries[cursor] : null;
  if (!d) return null;
  const inn = timeline.innings.find((i) => i.innings_no === d.innings_no);
  const side = inn?.batting_team_id === timeline.summary.team_a.team_season_id ? "a" : "b";
  const team = inn ? timeline.teams[inn.batting_team_id] : null;
  const data = oversUpTo(timeline, d.innings_no, cursor);
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        {team?.name}, {inningsLabel(d.innings_no, false)}: runs in each over
      </p>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="over" {...AXIS} />
            <YAxis allowDecimals={false} width={40} {...AXIS} />
            <Tooltip
              cursor={{ fill: "var(--muted)" }}
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelFormatter={(over) => `Over ${over}`}
              formatter={(value) => [`${value} runs`, ""]}
            />
            <Bar dataKey="runs" fill={SIDE_COLORS[side]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
