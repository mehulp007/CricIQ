"use client";

import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { SimDistribution, SimSideResult, SimulationResult } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { rate } from "@/lib/players";
import { SIM_SERIES, bowlingOvers, pct } from "@/lib/simulator";
import { cn } from "@/lib/utils";

const AXIS = { stroke: "var(--border)", tick: { fill: "var(--muted-foreground)", fontSize: 11 } };

function sideName(side: SimSideResult, fallback: string): string {
  return side.team?.name ?? fallback;
}

/** "Model simulation" chip: every number here is the model's, not a forecast. */
export function SimulationChip() {
  return (
    <span className="inline-flex items-center rounded-md border border-border px-2 py-0.5 text-[11px] tracking-wide text-muted-foreground uppercase">
      Model simulation
    </span>
  );
}

function WinShares({ result, names }: { result: SimulationResult; names: [string, string] }) {
  const a = result.a_win_pct;
  const b = result.b_win_pct;
  const tie = result.tie_pct;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-4">
        {(
          [
            [names[0], a, SIM_SERIES.a.color, "left"],
            null,
            [names[1], b, SIM_SERIES.b.color, "right"],
          ] as const
        ).map((entry, i) =>
          entry === null ? (
            <span key="tie" className="pb-1 text-center text-xs text-muted-foreground">
              tie {pct(tie)}
            </span>
          ) : (
            <div
              key={entry[0] + i}
              className={cn("flex min-w-0 flex-col gap-1", entry[3] === "right" && "items-end")}
            >
              <span className="flex items-center gap-2 truncate text-sm text-muted-foreground">
                <span
                  aria-hidden="true"
                  className="size-2.5 rounded-full"
                  style={{ background: entry[2] }}
                />
                {entry[0]}
              </span>
              <span className="font-mono text-4xl font-semibold tracking-tight tabular-nums">
                {pct(entry[1])}
              </span>
            </div>
          ),
        )}
      </div>
      <span aria-hidden="true" className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
        <span style={{ width: `${a}%`, background: SIM_SERIES.a.color }} />
        <span className="bg-muted-foreground/40" style={{ width: `${tie}%` }} />
        <span style={{ width: `${b}%`, background: SIM_SERIES.b.color }} />
      </span>
      <p className="text-xs text-muted-foreground">
        {result.simulations.toLocaleString("en-IN")} simulated matches
        {result.bat_first === null && ", each side batting first in half"} · Monte Carlo error ±
        {result.standard_error.toFixed(1)} points · {result.seconds.toFixed(1)} s
      </p>
    </div>
  );
}

interface BinPoint {
  bin: number;
  a: number;
  b: number;
}

function totalsData(a: SimDistribution | null | undefined, b: SimDistribution | null | undefined) {
  const map = new Map<number, BinPoint>();
  for (const [key, dist] of [
    ["a", a],
    ["b", b],
  ] as const) {
    for (const [bin, share] of dist?.bins ?? []) {
      const row = map.get(bin) ?? { bin, a: 0, b: 0 };
      row[key] = 100 * share;
      map.set(bin, row);
    }
  }
  return [...map.values()].sort((x, y) => x.bin - y.bin);
}

function BinTip({
  active,
  payload,
  names,
}: {
  active?: boolean;
  payload?: readonly { payload?: BinPoint }[];
  names: [string, string];
}) {
  const p = payload?.[0]?.payload;
  if (!active || !p) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-foreground">
        {p.bin}–{p.bin + 9} runs
      </p>
      {(["a", "b"] as const).map((k, i) => (
        <p key={k} className="flex items-center gap-2 text-muted-foreground">
          <span
            aria-hidden="true"
            className="size-2 rounded-full"
            style={{ background: SIM_SERIES[k].color }}
          />
          {names[i]}
          <span className="ml-auto pl-3 font-mono text-foreground tabular-nums">
            {p[k].toFixed(1)}%
          </span>
        </p>
      ))}
    </div>
  );
}

function rangeText(d: SimDistribution | null | undefined): string {
  return d ? `median ${d.p50}, 80% between ${d.p10} and ${d.p90}` : "never batted first";
}

function Totals({ result, names }: { result: SimulationResult; names: [string, string] }) {
  const [a, b] = result.sides;
  const data = totalsData(a.first_innings, b.first_innings);
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-1 text-sm" aria-label="Legend">
        {([a, b] as const).map((s, i) => (
          <li key={s.key} className="flex flex-wrap items-center gap-2">
            <span
              aria-hidden="true"
              className="size-2.5 rounded-sm"
              style={{ background: SIM_SERIES[s.key].color }}
            />
            <span className="font-medium">{names[i]}</span>
            <span className="text-muted-foreground">
              batting first: {rangeText(s.first_innings)}
            </span>
          </li>
        ))}
      </ul>
      <div
        className="h-56"
        role="img"
        aria-label={`Simulated first-innings totals: ${names[0]} ${rangeText(a.first_innings)}; ${names[1]} ${rangeText(b.first_innings)}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={2}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="bin" {...AXIS} tickLine={false} minTickGap={12} />
            <YAxis {...AXIS} tickLine={false} width={44} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip
              content={<BinTip names={names} />}
              cursor={{ fill: "var(--muted)", opacity: 0.4 }}
            />
            {(["a", "b"] as const).map((k) => (
              <Bar
                key={k}
                dataKey={k}
                fill={SIM_SERIES[k].color}
                radius={[3, 3, 0, 0]}
                isAnimationActive={false}
                maxBarSize={14}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
const td = "px-2 py-2 text-right font-mono tabular-nums";

function whole(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : String(value);
}

function range(low: number | null | undefined, high: number | null | undefined): string {
  return low === null || low === undefined || high === null || high === undefined
    ? "—"
    : `${low}–${high}`;
}

function Scorecard({ side, name }: { side: SimSideResult; name: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <h3 className="flex items-center gap-2 text-sm font-medium">
        <span
          aria-hidden="true"
          className="size-2.5 rounded-full"
          style={{ background: SIM_SERIES[side.key].color }}
        />
        {name}
        <span className="font-normal text-muted-foreground">
          · chases won {pct(side.chase_pct)}
        </span>
      </h3>
      <div className="overflow-x-auto" {...scrollRegion(`${name} simulated batting`)}>
        <table className="w-full min-w-[26rem] text-sm">
          <caption className="sr-only">{name}: typical simulated innings per batter</caption>
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                Batter
              </th>
              <th scope="col" className={th}>
                Runs
              </th>
              <th scope="col" className={th}>
                Balls
              </th>
              <th scope="col" className={th}>
                <abbr title="The middle half of their simulated scores" className="no-underline">
                  Range
                </abbr>
              </th>
              <th scope="col" className={th}>
                SR
              </th>
              <th scope="col" className={th}>
                50+
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {side.batters.map((b) => (
              <tr key={b.player_id}>
                <th scope="row" className="px-2 py-2 text-left font-normal">
                  <Link
                    href={`/players/${b.player_id}`}
                    className="underline-offset-4 hover:text-primary hover:underline"
                  >
                    {b.name}
                  </Link>
                  <span className="block text-[11px] text-muted-foreground">
                    bats in {pct(b.batted_pct, 0)}
                  </span>
                </th>
                <td className={cn(td, "font-semibold")}>{whole(b.runs)}</td>
                <td className={td}>{whole(b.balls)}</td>
                <td className={cn(td, "text-muted-foreground")}>
                  {range(b.runs_low, b.runs_high)}
                </td>
                <td className={td}>{rate(b.strike_rate, 1)}</td>
                <td className={td}>{pct(b.fifty_pct, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto" {...scrollRegion(`${name} simulated bowling`)}>
        <table className="w-full min-w-[26rem] text-sm">
          <caption className="sr-only">{name}: typical simulated figures per bowler</caption>
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                Bowler
              </th>
              <th scope="col" className={th}>
                Overs
              </th>
              <th scope="col" className={th}>
                Runs
              </th>
              <th scope="col" className={th}>
                Wkts
              </th>
              <th scope="col" className={th}>
                Econ
              </th>
              <th scope="col" className={th}>
                1+ wkt
              </th>
              <th scope="col" className={th}>
                3+ wkts
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {side.bowlers.map((b) => (
              <tr key={b.player_id}>
                <th scope="row" className="px-2 py-2 text-left font-normal">
                  <Link
                    href={`/players/${b.player_id}`}
                    className="underline-offset-4 hover:text-primary hover:underline"
                  >
                    {b.name}
                  </Link>
                  <span className="block text-[11px] text-muted-foreground">
                    bowls in {pct(b.bowled_pct, 0)}
                  </span>
                </th>
                <td className={td}>{bowlingOvers(b.balls)}</td>
                <td className={td}>{whole(b.runs)}</td>
                <td className={cn(td, "font-semibold")}>{whole(b.wickets)}</td>
                <td className={td}>{rate(b.economy)}</td>
                <td className={td}>{pct(b.wicket_pct, 0)}</td>
                <td className={td}>{pct(b.three_wicket_pct, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SimResults({ result }: { result: SimulationResult }) {
  const [a, b] = result.sides;
  const names: [string, string] = [sideName(a, "Team A"), sideName(b, "Team B")];
  return (
    <div className="flex flex-col gap-6">
      <section
        aria-labelledby="sim-result"
        className="flex flex-col gap-5 rounded-2xl border border-border bg-card/70 p-5 sm:p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="sim-result" className="text-lg font-semibold tracking-tight">
            Who wins
          </h2>
          <SimulationChip />
        </div>
        <WinShares result={result} names={names} />
        <p className="rounded-xl bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
          A simulation, not a forecast. Simulated before a ball was bowled, every 2025 and 2026
          match was called no better than a coin flip (see{" "}
          <Link
            href="/models?tab=simulator#simulator"
            className="text-primary underline-offset-4 hover:underline"
          >
            the backtest
          </Link>
          ): T20 matches between IPL sides are close to even. What the simulation is good for is the
          spread of scores, each player&apos;s likely contribution and what changes when you change
          the XI.
        </p>
        {result.margin_runs && (
          <p className="text-sm text-muted-foreground">
            When the side batting first wins, the median margin is{" "}
            <span className="font-mono text-foreground">{result.margin_runs.p50}</span> runs.
          </p>
        )}
      </section>

      <section
        aria-labelledby="sim-totals"
        className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5 sm:p-6"
      >
        <h2 id="sim-totals" className="text-lg font-semibold tracking-tight">
          First-innings totals
        </h2>
        <Totals result={result} names={names} />
      </section>

      <section
        aria-labelledby="sim-cards"
        className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5 sm:p-6"
      >
        <h2 id="sim-cards" className="text-lg font-semibold tracking-tight">
          The typical simulated scorecard
        </h2>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Each player&apos;s typical (median) innings in the simulated matches where they batted or
          bowled, so every score is in whole runs and wickets. Range is the middle half of their
          simulated scores: one innings in four was lower, one in four higher. 50+, 1+ and 3+ are
          shares of all simulated matches. Bowlers&apos; runs are off the bat; extras are the
          team&apos;s.
        </p>
        <div className="grid gap-8 xl:grid-cols-2">
          <Scorecard side={a} name={names[0]} />
          <Scorecard side={b} name={names[1]} />
        </div>
      </section>
    </div>
  );
}
