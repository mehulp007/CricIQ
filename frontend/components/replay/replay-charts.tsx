"use client";

import {
  Area,
  CartesianGrid,
  Line,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { WinProbabilityChart } from "@/components/replay/win-probability-chart";
import { PressureChart } from "@/components/replay/pressure-chart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Timeline } from "@/lib/api/types";
import { wormUpTo } from "@/lib/replay/engine";
import { projectionCone } from "@/lib/replay/projection";
import { inningsOvers, overTicks } from "@/lib/replay/win-probability";
import { AXIS } from "@/lib/chart-theme";
import { ChartTooltip, COLORS, Legend, sidesOf } from "@/components/replay/chart-parts";

export function ReplayCharts({
  timeline,
  cursor,
  onSeek,
}: {
  timeline: Timeline;
  cursor: number;
  onSeek: (index: number) => void;
}) {
  const hasModel = Boolean(timeline.win_probability);
  const hasPressure = timeline.deliveries.some(
    (d) => d.pressure !== null && d.pressure !== undefined,
  );
  const sides = sidesOf(timeline);
  const maxOvers = inningsOvers(timeline);

  const worm = sides.map((side) =>
    wormUpTo(timeline, side.inningsNo, cursor).map((p) => ({
      over: p.ball / 6,
      [side.key]: p.runs,
    })),
  );
  const target = timeline.innings.find((i) => i.innings_no === 2)?.target_runs;
  const chaseStarted = worm[1].length > 1;
  // The worm's x axis reads `over`.
  const cone = projectionCone(timeline, cursor).map(({ x, ...rest }) => ({ over: x, ...rest }));

  return (
    <section aria-label="Charts" className="panel">
      <Tabs defaultValue={hasModel ? "wp" : "worm"}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            {hasModel && <TabsTrigger value="wp">Win probability</TabsTrigger>}
            {hasPressure && <TabsTrigger value="pressure">Pressure</TabsTrigger>}
            <TabsTrigger value="worm">Worm</TabsTrigger>
          </TabsList>
          <Legend sides={sides} />
        </div>

        {hasModel && (
          <TabsContent value="wp" className="mt-4">
            <WinProbabilityChart timeline={timeline} cursor={cursor} onSeek={onSeek} />
          </TabsContent>
        )}

        {hasPressure && (
          <TabsContent value="pressure" className="mt-4">
            <PressureChart timeline={timeline} cursor={cursor} onSeek={onSeek} />
          </TabsContent>
        )}

        <TabsContent value="worm" className="mt-4">
          <p className="sr-only">
            Cumulative runs by over for each innings. During the first innings a shaded fan shows
            the projected 80% range of the final total.
          </p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="over"
                  type="number"
                  domain={[0, maxOvers]}
                  ticks={overTicks(maxOvers, maxOvers)}
                  {...AXIS}
                  allowDuplicatedCategory={false}
                />
                <YAxis {...AXIS} allowDecimals={false} width={48} />
                {target && chaseStarted && (
                  <ReferenceLine
                    y={target}
                    stroke="var(--muted-foreground)"
                    strokeDasharray="4 3"
                    label={{
                      value: `Target ${target}`,
                      position: "insideTopLeft",
                      fill: "var(--muted-foreground)",
                      fontSize: 11,
                    }}
                  />
                )}
                <Tooltip
                  cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
                  content={<ChartTooltip sides={sides} unit="worm" />}
                />
                {sides.map((side, i) => (
                  <Line
                    key={side.key}
                    data={worm[i]}
                    dataKey={side.key}
                    stroke={COLORS[side.key]}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--card)" }}
                    isAnimationActive={false}
                    name={side.name}
                  />
                ))}
                {cone.length > 0 && (
                  <>
                    <Area
                      data={cone}
                      dataKey="band"
                      type="linear"
                      stroke="none"
                      fill={COLORS.a}
                      fillOpacity={0.15}
                      isAnimationActive={false}
                      activeDot={false}
                      name="Projected 80% range"
                    />
                    <Line
                      data={cone}
                      dataKey="median"
                      type="linear"
                      stroke={COLORS.a}
                      strokeDasharray="4 4"
                      strokeWidth={1.5}
                      dot={false}
                      activeDot={false}
                      isAnimationActive={false}
                      name="Projected total"
                    />
                  </>
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {cone.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              Dashed line and fan: projected total and 80% range for {sides[0].name} (model
              estimate).
            </p>
          )}
        </TabsContent>
      </Tabs>
    </section>
  );
}
