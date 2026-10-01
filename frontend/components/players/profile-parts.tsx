import Link from "next/link";
import type { ReactNode } from "react";

import { TeamSwatch } from "@/components/match/team-badge";
import type {
  BattingInnings,
  BowlingInnings,
  DismissalCount,
  PercentileGroup,
  PhaseBatting,
  PhaseBowling,
} from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import {
  PLAYER_SERIES,
  dismissalLabel,
  formatMetric,
  formatWpa,
  isBetter,
  ordinal,
  rate,
  signed,
} from "@/lib/players";
import { cn } from "@/lib/utils";

/** A difference from par, coloured by whether it helps the player (the sign carries it too). */
export function ParDelta({
  delta,
  higherIsBetter = true,
  digits = 1,
  suffix = "",
}: {
  delta: number | null;
  higherIsBetter?: boolean;
  digits?: number;
  suffix?: string;
}) {
  if (delta === null || !Number.isFinite(delta))
    return <span className="text-muted-foreground">—</span>;
  const text = signed(delta, digits);
  const neutral = Number(Math.abs(delta).toFixed(digits)) === 0;
  return (
    <span
      className={cn(
        "font-mono tabular-nums",
        neutral
          ? "text-muted-foreground"
          : isBetter(delta, higherIsBetter)
            ? "text-positive"
            : "text-negative",
      )}
    >
      {text}
      {suffix}
    </span>
  );
}

export function StatTile({
  label,
  value,
  children,
}: {
  label: string;
  value: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card/70 p-4 sm:p-5">
      <p className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-2 font-mono text-2xl font-semibold tracking-tight tabular-nums sm:text-3xl">
        {value}
      </p>
      {children && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{children}</p>}
    </div>
  );
}

export function Panel({
  id,
  title,
  lede,
  children,
  className,
}: {
  id: string;
  title: string;
  lede?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      aria-labelledby={id}
      className={cn("min-w-0 rounded-2xl border border-border bg-card/70 p-5 sm:p-6", className)}
    >
      <h2 id={id} className="text-lg font-semibold tracking-tight">
        {title}
      </h2>
      {lede && (
        <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted-foreground">{lede}</p>
      )}
      <div className="mt-5">{children}</div>
    </section>
  );
}

// --------------------------------------------------------------------------- percentiles

export function PercentileBars({
  group,
  noun,
  window,
}: {
  group: PercentileGroup;
  noun: "batters" | "bowlers";
  window: string;
}) {
  return (
    <div className="flex flex-col gap-4">
      {!group.qualified && (
        <p className="rounded-lg border border-dashed border-border px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          Not ranked: percentiles need {group.min_balls} balls in the selected seasons, and this
          window has {group.balls}. The numbers are still shown.
        </p>
      )}
      <ul className="flex flex-col gap-4">
        {group.items.map((item) => (
          <li
            key={item.key}
            className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_13rem] sm:items-center sm:gap-4"
          >
            <div className="min-w-0">
              <p className="text-sm" title={item.description}>
                {item.label}
              </p>
              <p className="font-mono text-xs text-muted-foreground tabular-nums">
                {formatMetric(item)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span
                className="relative h-2 flex-1 rounded-full bg-muted"
                role="img"
                aria-label={
                  item.percentile === null
                    ? `${item.label}: not ranked`
                    : `${item.label}: ${ordinal(item.percentile)} percentile`
                }
              >
                {item.percentile !== null && (
                  <span
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: `${Math.max(item.percentile, 2)}%`,
                      background: PLAYER_SERIES.player.color,
                    }}
                  />
                )}
                <span
                  aria-hidden="true"
                  className="absolute -inset-y-1 left-1/2 w-px bg-foreground/30"
                />
              </span>
              <span className="w-12 text-right font-mono text-sm tabular-nums">
                {item.percentile === null ? (
                  <span
                    className="text-xs text-muted-foreground"
                    title={`Needs ${item.min_balls} balls; has ${item.balls}`}
                  >
                    n/a
                  </span>
                ) : (
                  ordinal(item.percentile)
                )}
              </span>
            </div>
          </li>
        ))}
      </ul>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Percentile among {group.population} {noun} with {group.min_balls}+ balls in {window}. Phase
        rows need 120 balls in that phase. The tick marks the median. Par is the league rate for the
        same season and phase, so eras and roles compare fairly.
      </p>
    </div>
  );
}

// --------------------------------------------------------------------------- phases

const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
const td = "px-2 py-2.5 text-right font-mono tabular-nums";

export function BattingPhaseTable({ rows }: { rows: PhaseBatting[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[30rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Phase
            </th>
            <th scope="col" className={th}>
              Balls
            </th>
            <th scope="col" className={th}>
              Runs
            </th>
            <th scope="col" className={th}>
              SR
            </th>
            <th scope="col" className={th}>
              Par
            </th>
            <th scope="col" className={th}>
              vs par
            </th>
            <th scope="col" className={th}>
              Avg
            </th>
            <th scope="col" className={th}>
              Dot %
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={r.phase}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                {r.label}
                <span className="block text-xs text-muted-foreground">
                  {Math.round(r.share * 100)}% of balls
                </span>
              </th>
              <td className={cn(td, "text-muted-foreground")}>{r.balls}</td>
              <td className={td}>{r.runs}</td>
              <td className={cn(td, "font-semibold")}>{rate(r.strike_rate, 1)}</td>
              <td className={cn(td, "text-muted-foreground")}>{rate(r.par_strike_rate, 1)}</td>
              <td className={td}>
                <ParDelta
                  delta={
                    r.strike_rate !== null && r.par_strike_rate !== null
                      ? r.strike_rate - r.par_strike_rate
                      : null
                  }
                />
              </td>
              <td className={td}>{rate(r.average, 1)}</td>
              <td className={cn(td, "text-muted-foreground")}>{rate(r.dot_pct, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BowlingPhaseTable({ rows }: { rows: PhaseBowling[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[30rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Phase
            </th>
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
              Par
            </th>
            <th scope="col" className={th}>
              vs par
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
          {rows.map((r) => (
            <tr key={r.phase}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                {r.label}
                <span className="block text-xs text-muted-foreground">
                  {Math.round(r.share * 100)}% of balls
                </span>
              </th>
              <td className={cn(td, "text-muted-foreground")}>
                {Math.floor(r.balls / 6)}.{r.balls % 6}
              </td>
              <td className={td}>{r.wickets}</td>
              <td className={cn(td, "font-semibold")}>{rate(r.economy)}</td>
              <td className={cn(td, "text-muted-foreground")}>{rate(r.par_economy)}</td>
              <td className={td}>
                <ParDelta
                  delta={
                    r.economy !== null && r.par_economy !== null ? r.economy - r.par_economy : null
                  }
                  higherIsBetter={false}
                  digits={2}
                />
              </td>
              <td className={td}>{rate(r.strike_rate, 1)}</td>
              <td className={cn(td, "text-muted-foreground")}>{rate(r.dot_pct, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------------------------------- dismissals

export function DismissalBars({ rows, total }: { rows: DismissalCount[]; total: number }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">None in these seasons.</p>;
  const max = Math.max(...rows.map((r) => r.count));
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <li
          key={r.kind}
          className="grid grid-cols-[8.5rem_minmax(0,1fr)_4.5rem] items-center gap-3"
        >
          <span className="truncate text-sm">{dismissalLabel(r.kind)}</span>
          <span className="h-2 rounded-full bg-muted" aria-hidden="true">
            <span
              className="block h-full rounded-full"
              style={{ width: `${(r.count / max) * 100}%`, background: PLAYER_SERIES.player.color }}
            />
          </span>
          <span className="text-right font-mono text-xs tabular-nums">
            {r.count}{" "}
            <span className="text-muted-foreground">({Math.round((100 * r.count) / total)}%)</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- recent innings

const RESULT: Record<string, string> = { won: "Won", lost: "Lost", no_result: "No result" };

function Opposition({ team }: { team: { franchise_id: string; name: string; color: string } }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-xs" title={team.name}>
      <TeamSwatch color={team.color} />
      {team.franchise_id}
    </span>
  );
}

function WpaCell({ wpa }: { wpa: number | null | undefined }) {
  if (wpa === null || wpa === undefined) return <span className="text-muted-foreground">—</span>;
  return <ParDelta delta={wpa * 100} digits={1} />;
}

export function RecentBattingTable({ innings }: { innings: BattingInnings[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[28rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Match
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              vs
            </th>
            <th scope="col" className={th}>
              Runs
            </th>
            <th scope="col" className={th}>
              4s/6s
            </th>
            <th scope="col" className={th}>
              Result
            </th>
            <th scope="col" className={th}>
              <abbr title="Change in the team's win probability while batting, in points">WPA</abbr>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {innings.map((i) => (
            <tr key={`${i.match_id}`}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                <Link
                  href={`/matches/${i.match_id}`}
                  className="underline-offset-4 hover:text-primary hover:underline"
                >
                  {formatDate(i.date)}
                </Link>
              </th>
              <td className="px-2 py-2.5">
                <Opposition team={i.opposition} />
              </td>
              <td className={cn(td, "font-semibold")}>
                {i.runs}
                {!i.is_out && "*"}
                <span className="font-normal text-muted-foreground"> ({i.balls})</span>
              </td>
              <td className={cn(td, "text-muted-foreground")}>
                {i.fours}/{i.sixes}
              </td>
              <td className={cn(td, "font-sans text-xs text-muted-foreground")}>
                {RESULT[i.result]}
              </td>
              <td className={td}>
                <WpaCell wpa={i.wpa} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RecentBowlingTable({ innings }: { innings: BowlingInnings[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[28rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Match
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              vs
            </th>
            <th scope="col" className={th}>
              Figures
            </th>
            <th scope="col" className={th}>
              Econ
            </th>
            <th scope="col" className={th}>
              Result
            </th>
            <th scope="col" className={th}>
              <abbr title="Change in the team's win probability while bowling, in points">WPA</abbr>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {innings.map((i) => (
            <tr key={`${i.match_id}`}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                <Link
                  href={`/matches/${i.match_id}`}
                  className="underline-offset-4 hover:text-primary hover:underline"
                >
                  {formatDate(i.date)}
                </Link>
              </th>
              <td className="px-2 py-2.5">
                <Opposition team={i.opposition} />
              </td>
              <td className={cn(td, "font-semibold")}>
                {i.wickets}/{i.runs}
                <span className="font-normal text-muted-foreground"> ({i.overs})</span>
              </td>
              <td className={cn(td, "text-muted-foreground")}>{rate(i.economy)}</td>
              <td className={cn(td, "font-sans text-xs text-muted-foreground")}>
                {RESULT[i.result]}
              </td>
              <td className={td}>
                <WpaCell wpa={i.wpa} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function WpaNote({ wpa, innings }: { wpa: number | null | undefined; innings: number }) {
  if (wpa === null || wpa === undefined) return null;
  return (
    <>
      {formatWpa(wpa)} wins over {innings} innings: the sum of every change in the team&apos;s
      chance of winning on this player&apos;s balls.
    </>
  );
}
