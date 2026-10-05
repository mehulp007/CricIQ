import Link from "next/link";
import type { ReactNode } from "react";

import { TeamSwatch } from "@/components/match/team-badge";
import { ParDelta } from "@/components/players/profile-parts";
import { RecordCell } from "@/components/teams/parts";
import type {
  OpponentRecord,
  RecordGroup,
  Swing,
  TeamBatter,
  TeamBowler,
  TeamPhase,
  TeamSeason,
  TeamTotal,
  VenueRecord,
} from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { formatDate } from "@/lib/format";
import { ordinal, rate } from "@/lib/players";
import { finishLabel, formatNrr, h2hHref } from "@/lib/teams";
import { cn } from "@/lib/utils";

const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
const td = "px-2 py-2.5 text-right font-mono tabular-nums";

// --------------------------------------------------------------------------- seasons

export function SeasonsTable({ seasons }: { seasons: TeamSeason[] }) {
  return (
    <div className="overflow-x-auto" {...scrollRegion("Season table")}>
      <table className="w-full min-w-[42rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Season
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              Finish
            </th>
            <th scope="col" className={th}>
              <abbr title="League stage: won–lost" className="no-underline">
                W–L
              </abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="No result" className="no-underline">
                NR
              </abbr>
            </th>
            <th scope="col" className={th}>
              Pts
            </th>
            <th scope="col" className={th}>
              <abbr title="Net run rate" className="no-underline">
                NRR
              </abbr>
            </th>
            <th scope="col" className={th}>
              Playoffs
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {[...seasons].reverse().map((s) => (
            <tr key={s.season}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                <Link
                  href={`/teams?season=${s.season}#table`}
                  className="font-mono tabular-nums underline-offset-4 hover:text-primary hover:underline"
                >
                  {s.season}
                </Link>
                <span className="ml-2 text-xs text-muted-foreground">{s.team_name}</span>
              </th>
              <td
                className={cn(
                  "px-2 py-2.5 text-left text-xs",
                  s.finish === "champion" ? "font-medium text-primary" : "text-muted-foreground",
                )}
              >
                {finishLabel(s.finish, s.exit_stage, s.position, s.teams)}
                {s.finish !== "league" && (
                  <span className="text-muted-foreground">
                    {" "}
                    · {ordinal(s.position)} in the league
                  </span>
                )}
              </td>
              <td className={td}>
                {s.won}–{s.lost}
              </td>
              <td className={td}>{s.no_result || ""}</td>
              <td className={td}>{s.points}</td>
              <td className={td}>{formatNrr(s.nrr)}</td>
              <td className={cn(td, "text-muted-foreground")}>
                {s.playoff_won + s.playoff_lost ? `${s.playoff_won}–${s.playoff_lost}` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------------------------------- results by situation

export function SplitsTable({ groups }: { groups: RecordGroup[] }) {
  return (
    <div className="overflow-x-auto" {...scrollRegion("Situation table")}>
      <table className="w-full min-w-[26rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Situation
            </th>
            <th scope="col" className={th}>
              Played
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              Won–lost · win %
            </th>
          </tr>
        </thead>
        {groups.map((g) => (
          <tbody key={g.key} className="border-b border-border last:border-0">
            <tr>
              <th
                scope="rowgroup"
                colSpan={3}
                className="px-2 pt-3 pb-1 text-left text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
              >
                {g.label}
              </th>
            </tr>
            {g.splits.map((s) => (
              <tr key={s.key}>
                <th scope="row" className="px-2 py-2 text-left font-normal">
                  {s.label}
                </th>
                <td className={td}>{s.record.played}</td>
                <td className="px-2 py-2">
                  <RecordCell record={s.record} />
                </td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}

// --------------------------------------------------------------------------- phases

function gap(
  value: number | null | undefined,
  par: number | null | undefined,
  sign: number,
): number | null {
  return value === null || value === undefined || par === null || par === undefined
    ? null
    : sign * (value - par);
}

function PhaseRows({ phases, role }: { phases: TeamPhase[]; role: "batting" | "bowling" }) {
  const batting = role === "batting";
  return (
    <div
      className="overflow-x-auto"
      {...scrollRegion(batting ? "Batting by phase" : "Bowling by phase")}
    >
      <table className="w-full min-w-[30rem] text-sm">
        <caption className="mb-2 text-left text-sm font-medium">
          {batting ? "Batting" : "Bowling"}
        </caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Phase
            </th>
            <th scope="col" className={th}>
              {batting ? "Run rate" : "Conceded"}
            </th>
            <th scope="col" className={th}>
              vs par
            </th>
            <th scope="col" className={th}>
              <abbr title="Balls per wicket" className="no-underline">
                Balls/wkt
              </abbr>
            </th>
            <th scope="col" className={th}>
              vs par
            </th>
            <th scope="col" className={th}>
              Boundary %
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {phases.map((p) => {
            const line = batting ? p.batting : p.bowling;
            // Signed so that positive always helps the side: batting wants a higher run rate
            // and more balls per wicket, bowling the opposite.
            const sign = batting ? 1 : -1;
            const rrDelta = gap(line.run_rate, line.par_run_rate, sign);
            const bpwDelta = gap(line.balls_per_wicket, line.par_balls_per_wicket, sign);
            return (
              <tr key={p.phase}>
                <th scope="row" className="px-2 py-2.5 text-left font-normal">
                  {p.label}
                  <span className="block text-[11px] text-muted-foreground">
                    {Math.floor(line.balls / 6)} overs
                  </span>
                </th>
                <td className={td}>{rate(line.run_rate)}</td>
                <td className={td}>
                  <ParDelta delta={rrDelta} digits={2} />
                </td>
                <td className={td}>{rate(line.balls_per_wicket, 1)}</td>
                <td className={td}>
                  <ParDelta delta={bpwDelta} />
                </td>
                <td className={td}>{rate(line.boundary_pct, 1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function PhaseTables({ phases }: { phases: TeamPhase[] }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <PhaseRows phases={phases} role="batting" />
      <PhaseRows phases={phases} role="bowling" />
    </div>
  );
}

// --------------------------------------------------------------------------- scoring

export function TotalLine({
  label,
  total,
}: {
  label: string;
  total: TeamTotal | null | undefined;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-muted/40 p-3">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      {total ? (
        <Link
          href={`/matches/${total.match_id}`}
          className="font-mono text-lg font-semibold tabular-nums underline-offset-4 hover:text-primary hover:underline"
        >
          {total.wickets === 10 ? total.runs : `${total.runs}/${total.wickets}`}
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">
            ({total.overs} ov)
          </span>
        </Link>
      ) : (
        <span className="text-muted-foreground">—</span>
      )}
      {total && (
        <span className="text-xs text-muted-foreground">
          v {total.opponent.franchise_id}, {formatDate(total.date)}
        </span>
      )}
    </div>
  );
}

export function MarginLine({
  label,
  margin,
}: {
  label: string;
  margin: { match_id: number; result_text: string; date: string } | null | undefined;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-muted/40 p-3">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      {margin ? (
        <>
          <Link
            href={`/matches/${margin.match_id}`}
            className="text-sm font-medium underline-offset-4 hover:text-primary hover:underline"
          >
            {margin.result_text}
          </Link>
          <span className="text-xs text-muted-foreground">{formatDate(margin.date)}</span>
        </>
      ) : (
        <span className="text-muted-foreground">—</span>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- players

export function TopBatters({ batters }: { batters: TeamBatter[] }) {
  return (
    <PlayerList
      title="Most runs"
      rows={batters.map((b) => ({
        id: b.player_id,
        name: b.name,
        main: `${b.runs}`,
        detail: `${b.innings} inns · SR ${rate(b.strike_rate, 1)} · avg ${rate(b.average, 1)}`,
      }))}
    />
  );
}

export function TopBowlers({ bowlers }: { bowlers: TeamBowler[] }) {
  return (
    <PlayerList
      title="Most wickets"
      rows={bowlers.map((b) => ({
        id: b.player_id,
        name: b.name,
        main: `${b.wickets}`,
        detail: `${b.innings} inns · econ ${rate(b.economy)} · avg ${rate(b.average, 1)}`,
      }))}
    />
  );
}

export function PlayerList({
  title,
  rows,
}: {
  title: string;
  rows: { id: string; name: string; main: string; detail: ReactNode }[];
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium">{title}</h3>
      {rows.length ? (
        <ol className="flex flex-col divide-y divide-border">
          {rows.map((r, i) => (
            <li key={r.id} className="flex items-baseline gap-3 py-2">
              <span className="w-4 font-mono text-xs text-muted-foreground tabular-nums">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <Link
                  href={`/players/${r.id}`}
                  className="text-sm underline-offset-4 hover:text-primary hover:underline"
                >
                  {r.name}
                </Link>
                <span className="block text-xs text-muted-foreground">{r.detail}</span>
              </span>
              <span className="font-mono text-sm font-semibold tabular-nums">{r.main}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-muted-foreground">None in these seasons.</p>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- opponents and venues

export function OpponentsTable({
  team,
  opponents,
  window,
}: {
  team: string;
  opponents: OpponentRecord[];
  window: { from?: number; to?: number };
}) {
  return (
    <div className="overflow-x-auto" {...scrollRegion("Record against each opponent")}>
      <table className="w-full min-w-[26rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Opponent
            </th>
            <th scope="col" className={th}>
              Played
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              Won–lost · win %
            </th>
            <th scope="col" className={th}>
              <span className="sr-only">Head to head</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {opponents.map((o) => (
            <tr key={o.opponent.franchise_id}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                <span className="inline-flex items-center gap-2">
                  <TeamSwatch color={o.opponent.color} />
                  {o.opponent.name}
                </span>
              </th>
              <td className={td}>{o.record.played}</td>
              <td className="px-2 py-2.5">
                <RecordCell record={o.record} />
              </td>
              <td className="px-2 py-2.5 text-right">
                <Link
                  href={h2hHref(team, o.opponent.franchise_id, window)}
                  className="text-xs text-primary underline-offset-4 hover:underline"
                  aria-label={`${team} against ${o.opponent.franchise_id}, head to head`}
                >
                  Head to head
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function VenuesTable({ venues }: { venues: VenueRecord[] }) {
  return (
    <div className="overflow-x-auto" {...scrollRegion("Record at each ground")}>
      <table className="w-full min-w-[26rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Ground
            </th>
            <th scope="col" className={th}>
              Played
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              Won–lost · win %
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {venues.map((v) => (
            <tr key={v.venue_id}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                {v.name}
                <span className="block text-xs text-muted-foreground">{v.city}</span>
              </th>
              <td className={td}>{v.record.played}</td>
              <td className="px-2 py-2.5">
                <RecordCell record={v.record} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------------------------------- swings

export function SwingList({ swings, kind }: { swings: Swing[]; kind: "comeback" | "collapse" }) {
  if (!swings.length)
    return <p className="text-sm text-muted-foreground">None in these seasons.</p>;
  return (
    <ol className="flex flex-col gap-2">
      {swings.map((s) => (
        <li key={s.match_id}>
          <Link
            href={`/matches/${s.match_id}?ball=${s.innings_no}.${s.seq_no}`}
            className="flex items-start gap-3 rounded-xl bg-muted/40 p-3 transition-colors hover:bg-muted/70"
          >
            <span
              className={cn(
                "w-14 shrink-0 font-mono text-lg font-semibold tabular-nums",
                kind === "comeback" ? "text-positive" : "text-negative",
              )}
            >
              {(100 * s.win_probability).toFixed(
                s.win_probability < 0.01 || s.win_probability > 0.99 ? 1 : 0,
              )}
              %
            </span>
            <span className="min-w-0 text-sm">
              <span className="block font-medium">
                {s.result_text}
                <span className="font-normal text-muted-foreground">
                  {" "}
                  v {s.opponent.franchise_id}, {s.season}
                </span>
              </span>
              <span className="block text-xs text-muted-foreground">
                {kind === "comeback" ? "Lowest point" : "Highest point"}: {s.situation}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
