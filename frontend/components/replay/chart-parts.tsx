"use client";

import type { Timeline } from "@/lib/api/types";

// Chart roles map to design tokens: side batting first = team A, chasing side = team B.
export const COLORS = { a: "var(--team-a)", b: "var(--team-b)" };

export interface Side {
  key: "a" | "b";
  name: string;
  short: string;
  inningsNo: number;
}

export function sidesOf(timeline: Timeline): Side[] {
  const { team_a, team_b } = timeline.summary;
  return [
    { key: "a", name: team_a.name, short: team_a.franchise_id, inningsNo: 1 },
    { key: "b", name: team_b.name, short: team_b.franchise_id, inningsNo: 2 },
  ];
}

export function Legend({ sides }: { sides: Side[] }) {
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

export function ChartTooltip({
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

export function WicketMarks(props: {
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
