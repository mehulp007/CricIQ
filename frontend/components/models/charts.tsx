"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { type BacktestRow, type ReliabilityBin, SERIES } from "@/lib/models";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

export function SeriesLegend() {
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Legend">
      {Object.entries(SERIES).map(([key, s]) => (
        <li key={key} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-2 w-4 rounded-full"
            style={{
              background: s.color,
              ...(key === "baseline" ? { opacity: 0.9 } : {}),
            }}
          />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

interface TipProps<T> {
  active?: boolean;
  payload?: readonly { payload?: T }[];
}

function Box({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; value: string; color?: string }[];
}) {
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2 text-muted-foreground">
          {r.color && (
            <span
              aria-hidden="true"
              className="size-2 rounded-full"
              style={{ background: r.color }}
            />
          )}
          {r.label}
          <span className="ml-auto pl-3 font-mono text-foreground tabular-nums">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

interface ReliabilityPoint {
  predicted: number;
  observed: number;
  count: number;
}

function ReliabilityTip({ active, payload }: TipProps<ReliabilityPoint>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <Box
      title={`Predicted ${row.predicted.toFixed(0)}%`}
      rows={[
        { label: "Actually won", value: `${row.observed.toFixed(0)}%` },
        { label: "Match states", value: row.count.toLocaleString("en-IN") },
      ]}
    />
  );
}

function BacktestTip({ active, payload }: TipProps<BacktestRow>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <Box
      title={`${row.season} season · ${row.matches} matches`}
      rows={[
        {
          label: SERIES.model.label,
          value: row.model_log_loss.toFixed(3),
          color: SERIES.model.color,
        },
        {
          label: SERIES.baseline.label,
          value: row.baseline_log_loss.toFixed(3),
          color: SERIES.baseline.color,
        },
      ]}
    />
  );
}

export function ReliabilityChart({
  model,
  baseline,
}: {
  model: ReliabilityBin[];
  baseline: ReliabilityBin[];
}) {
  const toPoints = (bins: ReliabilityBin[]): ReliabilityPoint[] =>
    bins.map((b) => ({
      predicted: b.predicted * 100,
      observed: b.observed * 100,
      count: b.count,
    }));
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: -8 }}>
          <CartesianGrid stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="predicted"
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(v: number) => `${v}%`}
            label={{
              value: "Predicted win probability",
              position: "insideBottom",
              offset: -8,
              fill: "var(--muted-foreground)",
              fontSize: 11,
            }}
            {...AXIS}
          />
          <YAxis
            type="number"
            dataKey="observed"
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(v: number) => `${v}%`}
            width={52}
            {...AXIS}
          />
          <ZAxis type="number" dataKey="count" range={[40, 40]} />
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 100, y: 100 },
            ]}
            stroke="var(--muted-foreground)"
            strokeDasharray="4 3"
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<ReliabilityTip />} />
          <Scatter
            name={SERIES.baseline.label}
            data={toPoints(baseline)}
            fill={SERIES.baseline.color}
            line={{ stroke: SERIES.baseline.color, strokeWidth: 2, strokeDasharray: "5 4" }}
            isAnimationActive={false}
          />
          <Scatter
            name={SERIES.model.label}
            data={toPoints(model)}
            fill={SERIES.model.color}
            line={{ stroke: SERIES.model.color, strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BacktestChart({ rows }: { rows: BacktestRow[] }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="season" {...AXIS} />
          <YAxis
            domain={["dataMin - 0.02", "dataMax + 0.02"]}
            tickFormatter={(v: number) => v.toFixed(2)}
            width={52}
            {...AXIS}
          />
          <Tooltip
            cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
            content={<BacktestTip />}
          />
          <Line
            dataKey="baseline_log_loss"
            name={SERIES.baseline.label}
            stroke={SERIES.baseline.color}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 3, fill: SERIES.baseline.color, strokeWidth: 0 }}
            isAnimationActive={false}
          />
          <Line
            dataKey="model_log_loss"
            name={SERIES.model.label}
            stroke={SERIES.model.color}
            strokeWidth={2}
            dot={{ r: 4, fill: SERIES.model.color, stroke: "var(--card)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
