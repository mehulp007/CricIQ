"use client";

import { useRouter } from "next/navigation";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BattingInnings, SeasonLine } from "@/lib/api/types";
import { useCompetition } from "@/components/competition/use-competition";
import { competitionPath } from "@/lib/competitions";
import { formatDate } from "@/lib/format";
import { PLAYER_SERIES, rate, signed } from "@/lib/players";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

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

export function ParLegend({ player = "Player", par = "Par" }: { player?: string; par?: string }) {
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Legend">
      <li className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="h-0.5 w-4 rounded-full"
          style={{ background: PLAYER_SERIES.player.color }}
        />
        {player}
      </li>
      <li className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="w-4 border-t-2 border-dashed"
          style={{ borderColor: PLAYER_SERIES.par.color }}
        />
        {par}
      </li>
    </ul>
  );
}

// --------------------------------------------------------------------------- seasons

interface SeasonPoint {
  season: number;
  value: number;
  rate: number | null;
  par: number | null;
  detail: { label: string; value: string }[];
}

function batPoints(seasons: SeasonLine[]): SeasonPoint[] {
  return seasons
    .filter((s) => s.batting)
    .map((s) => {
      const b = s.batting!;
      return {
        season: s.season,
        value: b.runs,
        rate: b.strike_rate ?? null,
        par: b.par_strike_rate ?? null,
        detail: [
          { label: "Innings", value: String(b.innings) },
          { label: "Runs", value: String(b.runs) },
          { label: "Average", value: rate(b.average, 1) },
          { label: "Highest", value: String(b.highest) },
        ],
      };
    });
}

function bowlPoints(seasons: SeasonLine[]): SeasonPoint[] {
  return seasons
    .filter((s) => s.bowling && s.bowling.balls > 0)
    .map((s) => {
      const b = s.bowling!;
      return {
        season: s.season,
        value: b.wickets,
        rate: b.economy ?? null,
        par: b.par_economy ?? null,
        detail: [
          { label: "Innings", value: String(b.innings) },
          { label: "Wickets", value: String(b.wickets) },
          { label: "Average", value: rate(b.average, 1) },
          { label: "Overs", value: `${Math.floor(b.balls / 6)}.${b.balls % 6}` },
        ],
      };
    });
}

function TotalTip({ active, payload }: TipProps<SeasonPoint>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return <Box title={`${row.season} season`} rows={row.detail} />;
}

function RateTip({
  active,
  payload,
  metric,
  digits,
}: TipProps<SeasonPoint> & { metric: string; digits: number }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const rows: { label: string; value: string; color?: string }[] = [
    { label: metric, value: rate(row.rate, digits), color: PLAYER_SERIES.player.color },
    { label: "Par", value: rate(row.par, digits), color: PLAYER_SERIES.par.color },
  ];
  if (row.rate !== null && row.par !== null) {
    rows.push({ label: "Difference", value: signed(row.rate - row.par, digits) });
  }
  return <Box title={`${row.season} season`} rows={rows} />;
}

function SeasonTotals({ points, label }: { points: SeasonPoint[]; label: string }) {
  return (
    <div className="h-56" role="img" aria-label={`${label} by season`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="season" {...AXIS} tickLine={false} minTickGap={8} />
          <YAxis {...AXIS} tickLine={false} allowDecimals={false} width={48} />
          <Tooltip content={<TotalTip />} cursor={{ fill: "var(--muted)", opacity: 0.4 }} />
          <Bar
            dataKey="value"
            name={label}
            fill={PLAYER_SERIES.player.color}
            radius={[4, 4, 0, 0]}
            maxBarSize={28}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SeasonRates({
  points,
  label,
  digits,
}: {
  points: SeasonPoint[];
  label: string;
  digits: number;
}) {
  return (
    <div className="h-56" role="img" aria-label={`${label} against par by season`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="season" {...AXIS} tickLine={false} minTickGap={8} />
          <YAxis
            {...AXIS}
            tickLine={false}
            width={48}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => v.toFixed(digits === 2 ? 1 : 0)}
          />
          <Tooltip content={<RateTip metric={label} digits={digits} />} />
          <Line
            dataKey="par"
            name="Par"
            stroke={PLAYER_SERIES.par.color}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            dataKey="rate"
            name={label}
            stroke={PLAYER_SERIES.player.color}
            strokeWidth={2}
            dot={{ r: 3, strokeWidth: 0, fill: PLAYER_SERIES.player.color }}
            activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }}
            connectNulls
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SeasonCharts({
  seasons,
  role,
}: {
  seasons: SeasonLine[];
  role: "batting" | "bowling";
}) {
  const batting = role === "batting";
  const points = batting ? batPoints(seasons) : bowlPoints(seasons);
  const total = batting ? "Runs" : "Wickets";
  const rateLabel = batting ? "Strike rate" : "Economy";
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <figure className="flex min-w-0 flex-col gap-2">
        <figcaption className="text-xs text-muted-foreground">{total} by season</figcaption>
        <SeasonTotals points={points} label={total} />
      </figure>
      <figure className="flex min-w-0 flex-col gap-2">
        <figcaption className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            {rateLabel} against par{!batting && " (lower is better)"}
          </span>
          <ParLegend player={rateLabel} />
        </figcaption>
        <SeasonRates points={points} label={rateLabel} digits={batting ? 1 : 2} />
      </figure>
    </div>
  );
}

// --------------------------------------------------------------------------- form

interface FormPoint {
  index: number;
  runs: number;
  notOut: boolean;
  innings: BattingInnings;
}

function FormTip({ active, payload }: TipProps<FormPoint>) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const i = row.innings;
  return (
    <Box
      title={`${formatDate(i.date)} vs ${i.opposition.franchise_id}`}
      rows={[
        { label: "Runs", value: `${i.runs}${i.is_out ? "" : "*"} (${i.balls})` },
        { label: "Batting at", value: `No. ${i.position}` },
        { label: "Result", value: { won: "Won", lost: "Lost", no_result: "No result" }[i.result] },
        ...(i.wpa !== null && i.wpa !== undefined
          ? [{ label: "Win prob. added", value: `${signed(i.wpa * 100)} pts` }]
          : []),
      ]}
    />
  );
}

/** Runs in each of the most recent innings, oldest to newest; a bar opens that replay. */
export function FormChart({ innings }: { innings: BattingInnings[] }) {
  const router = useRouter();
  const competition = useCompetition();
  const points: FormPoint[] = [...innings]
    .reverse()
    .map((i, index) => ({ index: index + 1, runs: i.runs, notOut: !i.is_out, innings: i }));
  return (
    <div className="flex flex-col gap-2">
      <div
        className="h-52"
        role="img"
        aria-label={`Runs in the last ${points.length} innings: ${points
          .map((p) => `${p.runs}${p.notOut ? "*" : ""}`)
          .join(", ")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} margin={{ top: 16, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="index" {...AXIS} tickLine={false} tick={false} />
            <YAxis {...AXIS} tickLine={false} allowDecimals={false} width={48} />
            <Tooltip content={<FormTip />} cursor={{ fill: "var(--muted)", opacity: 0.4 }} />
            <Bar
              dataKey="runs"
              radius={[4, 4, 0, 0]}
              maxBarSize={24}
              minPointSize={2}
              isAnimationActive={false}
              className="cursor-pointer"
              onClick={(entry: { payload?: FormPoint }) => {
                const id = entry.payload?.innings.match_id;
                if (id) router.push(competitionPath(competition, `/matches/${id}`));
              }}
            >
              {points.map((p) => (
                <Cell
                  key={p.index}
                  fill={PLAYER_SERIES.player.color}
                  fillOpacity={p.notOut ? 0.55 : 1}
                />
              ))}
              <LabelList
                dataKey="notOut"
                position="top"
                formatter={(v: unknown) => (v ? "*" : "")}
                style={{ fill: "var(--muted-foreground)", fontSize: 12 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted-foreground">
        Oldest to newest. Lighter bars marked * are not-out innings. Select a bar to open the
        replay.
      </p>
    </div>
  );
}
