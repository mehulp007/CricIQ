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

import {
  type BacktestRow,
  type ProjectionBacktestRow,
  type ReliabilityBin,
  SERIES,
} from "@/lib/models";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

export function SeriesLegend({ baseline = SERIES.baseline.label }: { baseline?: string }) {
  const labels = { model: SERIES.model.label, baseline };
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
          {labels[key as keyof typeof labels]}
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

interface LevelPoint {
  level: number;
  observed: number;
}

function LevelTip({ active, payload }: TipProps<LevelPoint>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <Box
      title={`${row.level}% line`}
      rows={[{ label: "Totals at or below it", value: `${row.observed.toFixed(1)}%` }]}
    />
  );
}

/** Each quantile's stated level against the share of real totals that fell below it. */
export function LevelCalibrationChart({ rows }: { rows: { level: number; observed: number }[] }) {
  const data: LevelPoint[] = rows.map((r) => ({
    level: r.level * 100,
    observed: r.observed * 100,
  }));
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: -8 }}>
          <CartesianGrid stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="level"
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(v: number) => `${v}%`}
            label={{
              value: "Quantile level",
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
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 100, y: 100 },
            ]}
            stroke="var(--muted-foreground)"
            strokeDasharray="4 3"
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<LevelTip />} />
          <Scatter
            data={data}
            fill={SERIES.model.color}
            line={{ stroke: SERIES.model.color, strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function ErrorTip({ active, payload }: TipProps<ProjectionBacktestRow>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <Box
      title={`${row.season} · average total ${row.mean_total.toFixed(0)}`}
      rows={[
        {
          label: SERIES.model.label,
          value: `${row.mae.toFixed(1)} runs`,
          color: SERIES.model.color,
        },
        {
          label: "Par + spread",
          value: `${row.par_mae.toFixed(1)} runs`,
          color: SERIES.baseline.color,
        },
        { label: "80% range covered", value: `${(row.coverage80 * 100).toFixed(0)}%` },
      ]}
    />
  );
}

/** Median error of the projection by season, against par for the era. */
export function ProjectionBacktestChart({ rows }: { rows: ProjectionBacktestRow[] }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="season" {...AXIS} />
          <YAxis
            domain={["dataMin - 1", "dataMax + 1"]}
            tickFormatter={(v: number) => v.toFixed(0)}
            width={52}
            {...AXIS}
          />
          <Tooltip
            cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
            content={<ErrorTip />}
          />
          <Line
            dataKey="par_mae"
            stroke={SERIES.baseline.color}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 3, fill: SERIES.baseline.color, strokeWidth: 0 }}
            isAnimationActive={false}
          />
          <Line
            dataKey="mae"
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

// ------------------------------------------------------------------ ball outcome

export interface BallBacktestRow {
  season: number;
  balls: number;
  model_log_loss: number;
  baseline_log_loss: number;
}

function BallBacktestTip({ active, payload }: TipProps<BallBacktestRow>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <Box
      title={`${row.season} season · ${row.balls.toLocaleString("en-IN")} balls`}
      rows={[
        {
          label: "CricIQ ball model",
          value: row.model_log_loss.toFixed(4),
          color: SERIES.model.color,
        },
        {
          label: "Phase and wickets",
          value: row.baseline_log_loss.toFixed(4),
          color: SERIES.baseline.color,
        },
      ]}
    />
  );
}

/** Log loss per season for the ball model against the phase-and-wickets frequencies. */
export function BallBacktestChart({ rows }: { rows: BallBacktestRow[] }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="season" {...AXIS} />
          <YAxis
            domain={["dataMin - 0.005", "dataMax + 0.005"]}
            tickFormatter={(v: number) => v.toFixed(3)}
            width={56}
            {...AXIS}
          />
          <Tooltip
            cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }}
            content={<BallBacktestTip />}
          />
          <Line
            dataKey="baseline_log_loss"
            stroke={SERIES.baseline.color}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 3, fill: SERIES.baseline.color, strokeWidth: 0 }}
            isAnimationActive={false}
          />
          <Line
            dataKey="model_log_loss"
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

interface OutcomeBin {
  predicted: number;
  observed: number;
  count: number;
}

function OutcomeTip({ active, payload }: TipProps<OutcomeBin>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <Box
      title={`Predicted ${row.predicted.toFixed(1)}%`}
      rows={[
        { label: "Actually happened", value: `${row.observed.toFixed(1)}%` },
        { label: "Balls", value: row.count.toLocaleString("en-IN") },
      ]}
    />
  );
}

/** Predicted probability deciles for one outcome against how often it happened. */
export function OutcomeCalibrationChart({ bins }: { bins: OutcomeBin[] }) {
  const data = bins.map((b) => ({
    predicted: b.predicted * 100,
    observed: b.observed * 100,
    count: b.count,
  }));
  const top = Math.max(...data.flatMap((d) => [d.predicted, d.observed])) * 1.1;
  const domain: [number, number] = [0, Math.max(Math.ceil(top / 5) * 5, 5)];
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: -8 }}>
          <CartesianGrid stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="predicted"
            domain={domain}
            tickFormatter={(v: number) => `${v}%`}
            label={{
              value: "Predicted probability",
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
            domain={domain}
            tickFormatter={(v: number) => `${v}%`}
            width={52}
            {...AXIS}
          />
          <ZAxis type="number" dataKey="count" range={[40, 40]} />
          <ReferenceLine
            segment={[
              { x: domain[0], y: domain[0] },
              { x: domain[1], y: domain[1] },
            ]}
            stroke="var(--muted-foreground)"
            strokeDasharray="4 3"
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<OutcomeTip />} />
          <Scatter
            data={data}
            fill={SERIES.model.color}
            line={{ stroke: SERIES.model.color, strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
