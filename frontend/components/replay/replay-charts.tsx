"use client";

import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
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
import { oversUpTo, wormUpTo } from "@/lib/replay/engine";
import { projectionCone } from "@/lib/replay/projection";

// Chart roles map to design tokens: side batting first = team A, chasing side = team B.
const COLORS = { a: "var(--team-a)", b: "var(--team-b)" };
const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

interface Side {
  key: "a" | "b";
  name: string;
  short: string;
  inningsNo: number;
}

function sidesOf(timeline: Timeline): Side[] {
  const { team_a, team_b } = timeline.summary;
  return [
    { key: "a", name: team_a.name, short: team_a.franchise_id, inningsNo: 1 },
    { key: "b", name: team_b.name, short: team_b.franchise_id, inningsNo: 2 },
  ];
}

function Legend({ sides }: { sides: Side[] }) {
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Legend">
      {sides.map((side) => (
        <li key={side.key} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-2 w-4 rounded-full"
            style={{ background: COLORS[side.key] }}
          />
          {side.name}
        </li>
      ))}
    </ul>
  );
}

interface TooltipEntry {
  dataKey?: string | number;
  value?: number | string;
  payload?: Record<string, number | undefined>;
}

function ChartTooltip({
  active,
  payload,
  label,
  sides,
  unit,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: number | string;
  sides: Side[];
  unit: "worm" | "manhattan";
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        {unit === "worm"
          ? `After ${Number(label).toFixed(1).replace(".0", "")} overs`
          : `Over ${label}`}
      </p>
      {payload.map((entry) => {
        const side = sides.find((s) => s.key === entry.dataKey);
        if (!side || entry.value === undefined) return null;
        const wickets = unit === "manhattan" ? entry.payload?.[`${side.key}W`] : undefined;
        return (
          <p key={side.key} className="flex items-center gap-2 text-muted-foreground">
            <span
              aria-hidden="true"
              className="size-2 rounded-full"
              style={{ background: COLORS[side.key] }}
            />
            {side.short}
            <span className="ml-auto font-mono text-foreground tabular-nums">
              {entry.value}
              {unit === "manhattan" ? " runs" : ""}
              {wickets ? ` · ${wickets} wkt${wickets > 1 ? "s" : ""}` : ""}
            </span>
          </p>
        );
      })}
    </div>
  );
}

function WicketMarks(props: {
  x?: number | string;
  y?: number | string;
  width?: number | string;
  value?: number | string;
}) {
  const count = Number(props.value ?? 0);
  if (!count) return null;
  const cx = Number(props.x) + Number(props.width) / 2;
  const top = Number(props.y);
  return (
    <g aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <circle
          key={i}
          cx={cx}
          cy={top - 6 - i * 9}
          r={3.5}
          fill="var(--wicket)"
          stroke="var(--card)"
          strokeWidth={1.5}
        />
      ))}
    </g>
  );
}

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
  const maxOvers = 20;

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
    <section aria-label="Charts" className="rounded-2xl border border-border bg-card/70 p-5">
      <Tabs defaultValue={hasModel ? "wp" : "worm"}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            {hasModel && <TabsTrigger value="wp">Win probability</TabsTrigger>}
            {hasPressure && <TabsTrigger value="pressure">Pressure</TabsTrigger>}
            <TabsTrigger value="worm">Worm</TabsTrigger>
            <TabsTrigger value="manhattan">Manhattan</TabsTrigger>
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
                  ticks={[0, 5, 10, 15, 20]}
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

        <TabsContent value="manhattan" className="mt-4">
          <p className="sr-only">Runs scored in each over, with wickets marked above the bars.</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={manhattan}
                barGap={2}
                margin={{ top: 24, right: 12, bottom: 0, left: -12 }}
              >
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="over" {...AXIS} interval={1} />
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
          </div>
        </TabsContent>
      </Tabs>
    </section>
  );
}
