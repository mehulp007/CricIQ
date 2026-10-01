"use client";

import { useState } from "react";

import { TeamSwatch } from "@/components/match/team-badge";
import { ParDelta } from "@/components/players/profile-parts";
import type { BattingSplitGroup, BowlingSplitGroup } from "@/lib/api/types";
import { SMALL_SAMPLE_BALLS, rate } from "@/lib/players";
import { cn } from "@/lib/utils";

const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
const td = "px-2 py-2.5 text-right font-mono tabular-nums";

function GroupPicker({
  groups,
  active,
  onChange,
  label,
}: {
  groups: { key: string; label: string }[];
  active: string;
  onChange: (key: string) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {groups.map((g) => (
        <button
          key={g.key}
          type="button"
          aria-pressed={g.key === active}
          onClick={() => onChange(g.key)}
          className={cn(
            "h-8 rounded-lg border px-3 text-xs transition-colors",
            g.key === active
              ? "border-primary/50 bg-primary/10 text-foreground"
              : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          {g.label}
        </button>
      ))}
    </div>
  );
}

function SplitLabel({
  label,
  color,
  small,
}: {
  label: string;
  color?: string | null;
  small: boolean;
}) {
  return (
    <span className="flex items-center gap-2">
      {color && <TeamSwatch color={color} />}
      <span className="min-w-0">
        {label}
        {small && (
          <span className="ml-2 rounded-full border border-border px-1.5 py-px text-[10px] text-muted-foreground">
            small sample
          </span>
        )}
      </span>
    </span>
  );
}

export function BattingSplits({ groups }: { groups: BattingSplitGroup[] }) {
  const [active, setActive] = useState(groups[0]?.key ?? "phase");
  const group = groups.find((g) => g.key === active) ?? groups[0];
  if (!group) return null;
  const inningsLevel = group.rows.some((r) => r.innings !== null);
  return (
    <div className="flex flex-col gap-4">
      <GroupPicker
        groups={groups}
        active={group.key}
        onChange={setActive}
        label="Split batting by"
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <caption className="sr-only">Batting split by {group.label.toLowerCase()}</caption>
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                {group.label}
              </th>
              {inningsLevel && (
                <th scope="col" className={th}>
                  Inns
                </th>
              )}
              <th scope="col" className={th}>
                Balls
              </th>
              <th scope="col" className={th}>
                Runs
              </th>
              <th scope="col" className={th}>
                Avg
              </th>
              <th scope="col" className={th}>
                SR
              </th>
              <th scope="col" className={th}>
                vs par
              </th>
              <th scope="col" className={th}>
                Dot %
              </th>
              <th scope="col" className={th}>
                <abbr title="Fours and sixes per 100 balls">4s+6s %</abbr>
              </th>
              {inningsLevel && (
                <th scope="col" className={th}>
                  <abbr title="Highest score">HS</abbr>
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {group.rows.map((r) => {
              const small = r.balls < SMALL_SAMPLE_BALLS;
              return (
                <tr key={r.key} className={cn(small && "text-muted-foreground")}>
                  <th scope="row" className="px-2 py-2.5 text-left font-normal">
                    <SplitLabel label={r.label} color={r.color} small={small} />
                  </th>
                  {inningsLevel && <td className={td}>{r.innings}</td>}
                  <td className={cn(td, "text-muted-foreground")}>{r.balls}</td>
                  <td className={td}>{r.runs}</td>
                  <td className={td}>{rate(r.average, 1)}</td>
                  <td className={cn(td, "font-semibold")}>{rate(r.strike_rate, 1)}</td>
                  <td className={td}>
                    <ParDelta
                      delta={
                        r.strike_rate !== null && r.par_strike_rate !== null
                          ? r.strike_rate - r.par_strike_rate
                          : null
                      }
                    />
                  </td>
                  <td className={cn(td, "text-muted-foreground")}>{rate(r.dot_pct, 1)}</td>
                  <td className={cn(td, "text-muted-foreground")}>{rate(r.boundary_pct, 1)}</td>
                  {inningsLevel && <td className={td}>{r.highest ?? "—"}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BowlingSplits({ groups }: { groups: BowlingSplitGroup[] }) {
  const [active, setActive] = useState(groups[0]?.key ?? "phase");
  const group = groups.find((g) => g.key === active) ?? groups[0];
  if (!group) return null;
  const inningsLevel = group.rows.some((r) => r.innings !== null);
  return (
    <div className="flex flex-col gap-4">
      <GroupPicker
        groups={groups}
        active={group.key}
        onChange={setActive}
        label="Split bowling by"
      />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <caption className="sr-only">Bowling split by {group.label.toLowerCase()}</caption>
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                {group.label}
              </th>
              {inningsLevel && (
                <th scope="col" className={th}>
                  Inns
                </th>
              )}
              <th scope="col" className={th}>
                Overs
              </th>
              <th scope="col" className={th}>
                Wkts
              </th>
              <th scope="col" className={th}>
                Econ
              </th>
              <th scope="col" className={th}>
                vs par
              </th>
              <th scope="col" className={th}>
                Avg
              </th>
              <th scope="col" className={th}>
                SR
              </th>
              <th scope="col" className={th}>
                Dot %
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {group.rows.map((r) => {
              const small = r.balls < SMALL_SAMPLE_BALLS;
              return (
                <tr key={r.key} className={cn(small && "text-muted-foreground")}>
                  <th scope="row" className="px-2 py-2.5 text-left font-normal">
                    <SplitLabel label={r.label} color={r.color} small={small} />
                  </th>
                  {inningsLevel && <td className={td}>{r.innings}</td>}
                  <td className={cn(td, "text-muted-foreground")}>
                    {Math.floor(r.balls / 6)}.{r.balls % 6}
                  </td>
                  <td className={td}>{r.wickets}</td>
                  <td className={cn(td, "font-semibold")}>{rate(r.economy)}</td>
                  <td className={td}>
                    <ParDelta
                      delta={
                        r.economy !== null && r.par_economy !== null
                          ? r.economy - r.par_economy
                          : null
                      }
                      higherIsBetter={false}
                      digits={2}
                    />
                  </td>
                  <td className={td}>{rate(r.average, 1)}</td>
                  <td className={td}>{rate(r.strike_rate, 1)}</td>
                  <td className={cn(td, "text-muted-foreground")}>{rate(r.dot_pct, 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
