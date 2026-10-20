"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartTooltip, COLORS, sidesOf, WicketMarks } from "@/components/replay/chart-parts";
import type { Timeline } from "@/lib/api/types";
import { AXIS } from "@/lib/chart-theme";
import { oversUpTo } from "@/lib/replay/engine";
import { inningsOvers } from "@/lib/replay/win-probability";

/** Runs in each over of both innings as bars, with wickets marked above them. */
export function ManhattanChart({ timeline, cursor }: { timeline: Timeline; cursor: number }) {
  const sides = sidesOf(timeline);
  const maxOvers = inningsOvers(timeline);
  const manhattan = Array.from(
    { length: maxOvers },
    (_, i) => ({ over: i + 1 }) as Record<string, number>,
  );
  sides.forEach((side) => {
    for (const point of oversUpTo(timeline, side.inningsNo, cursor)) {
      if (point.over > maxOvers) continue;
      manhattan[point.over - 1][side.key] = point.runs;
      manhattan[point.over - 1][`${side.key}W`] = point.wickets;
    }
  });
  return (
    <>
      <p className="sr-only">Runs scored in each over, with wickets marked above the bars.</p>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={manhattan} barGap={2} margin={{ top: 24, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="over" {...AXIS} interval={maxOvers > 20 ? 4 : 1} />
          <YAxis {...AXIS} allowDecimals={false} width={48} />
          <Tooltip
            cursor={{ fill: "var(--muted)", opacity: 0.4 }}
            content={<ChartTooltip sides={sides} unit="manhattan" />}
          />
          {sides.map((side) => (
            <Bar
              key={side.key}
              dataKey={side.key}
              fill={COLORS[side.key]}
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
              name={side.name}
            >
              <LabelList dataKey={`${side.key}W`} content={<WicketMarks />} />
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}
