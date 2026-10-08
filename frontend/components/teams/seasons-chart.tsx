"use client";

import { SeasonLabel } from "@/components/competition/season-label";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCompetition } from "@/components/competition/use-competition";
import { seasonLabel } from "@/lib/competitions";
import type { Finish, TeamSeason } from "@/lib/api/types";
import { finishLabel } from "@/lib/teams";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

/** Bar opacity by how far the season went; the finish is also named in the tooltip and table. */
const FINISH_OPACITY: Record<Finish, number> = {
  champion: 1,
  runner_up: 0.8,
  playoffs: 0.6,
  league: 0.3,
};

interface Point extends TeamSeason {
  win_pct: number;
}

function Tip({ active, payload }: { active?: boolean; payload?: readonly { payload?: Point }[] }) {
  const p = payload?.[0]?.payload;
  if (!active || !p) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        <SeasonLabel season={p.season} /> · {p.team_name}
      </p>
      <p className="text-muted-foreground">
        League:{" "}
        <span className="font-mono text-foreground">
          {p.won}–{p.lost}
        </span>
        {(p.drawn ?? 0) > 0 && ` · ${p.drawn} drawn`}
        {p.no_result > 0 && ` · ${p.no_result} NR`} ·{" "}
        <span className="font-mono text-foreground">{p.win_pct.toFixed(0)}%</span>
      </p>
      <p className="text-muted-foreground">
        {finishLabel(p.finish, p.exit_stage, p.position, p.teams)}
      </p>
    </div>
  );
}

// One series, so one chart colour: franchise colours are too dark to read on dark surfaces.
const color = "var(--chart-3)";

/** League-stage win percentage each season, shaded by how far the side went. */
export function SeasonsChart({ seasons }: { seasons: TeamSeason[] }) {
  const competition = useCompetition();
  const data: Point[] = seasons.map((s) => ({
    ...s,
    // Tests' draws count among the matches played.
    win_pct:
      s.won + s.lost + (s.drawn ?? 0) ? (100 * s.won) / (s.won + s.lost + (s.drawn ?? 0)) : 0,
  }));
  const legend: [Finish, string][] = [
    ["champion", "Champions"],
    ["runner_up", "Runners-up"],
    ["playoffs", "Playoffs"],
    ["league", "League stage"],
  ];
  return (
    <div className="flex flex-col gap-3">
      <ul
        className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"
        aria-label="Legend"
      >
        {legend.map(([finish, label]) => (
          <li key={finish} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="size-2.5 rounded-sm"
              style={{ background: color, opacity: FINISH_OPACITY[finish] }}
            />
            {label}
          </li>
        ))}
      </ul>
      <div
        className="h-56"
        role="img"
        aria-label="League-stage win percentage in each season, shaded by finish; the season table below lists every value"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="season"
              {...AXIS}
              tickLine={false}
              minTickGap={8}
              tickFormatter={(s: number) => seasonLabel(competition, s)}
            />
            <YAxis
              {...AXIS}
              tickLine={false}
              width={44}
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(v: number) => `${v}%`}
            />
            <ReferenceLine y={50} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
            <Tooltip content={<Tip />} cursor={{ fill: "var(--muted)", opacity: 0.4 }} />
            <Bar dataKey="win_pct" radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={28}>
              {data.map((d) => (
                <Cell key={d.season} fill={color} fillOpacity={FINISH_OPACITY[d.finish]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
