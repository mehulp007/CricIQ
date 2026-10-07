import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { MatchCard } from "@/components/match/match-card";
import { TeamSwatch } from "@/components/match/team-badge";
import { Panel } from "@/components/players/profile-parts";
import { SeasonWindow } from "@/components/players/season-window";
import { PlayerList, TotalLine } from "@/components/teams/team-sections";
import { TeamPicker } from "@/components/teams/team-picker";
import { ApiError, getHeadToHead, getTeams } from "@/lib/api/client";
import type { H2HRecord, HeadToHead, TeamsOverview } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { COMPARE_SERIES } from "@/lib/compare";
import { parseSeason, rate } from "@/lib/players";
import { getCompetition, isCompetitionId, type CompetitionId } from "@/lib/competitions";
import { expectationVerdict, h2hHref, parseTeamId, seasonSpan } from "@/lib/teams";
import { cn } from "@/lib/utils";
import { CompetitionLink } from "@/components/competition/competition-link";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/teams/h2h">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  const sides = c.teamType === "national" ? "sides" : "franchises";
  return {
    title: `${c.label} head to head`,
    description: `Any two ${c.label} ${sides}' record against each other, by season, ground and batting order, set against what each side's form going into those matches predicted.`,
  };
}

// Pairs to start from, by competition; the busiest pairs where none are listed.
const SUGGESTIONS: Partial<Record<CompetitionId, [string, string][]>> = {
  ipl: [
    ["MI", "CSK"],
    ["CSK", "RCB"],
    ["MI", "KKR"],
    ["RCB", "KKR"],
    ["RR", "SRH"],
    ["GT", "LSG"],
  ],
  t20i: [
    ["IND", "PAK"],
    ["AUS", "ENG"],
    ["IND", "AUS"],
    ["NZ", "SA"],
    ["ENG", "PAK"],
    ["WI", "SL"],
  ],
};

async function load(
  competition: CompetitionId,
  a: string,
  b: string,
  from: number | undefined,
  to: number | undefined,
): Promise<HeadToHead | null> {
  try {
    return await getHeadToHead(competition, a, b, { from, to });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) return null;
    throw error;
  }
}

function Tally({ h2h }: { h2h: HeadToHead }) {
  const r = h2h.record;
  const side = (team: HeadToHead["a"], wins: number, color: string, align: "left" | "right") => (
    <div className={cn("flex min-w-0 flex-col gap-1", align === "right" && "items-end text-right")}>
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: color }} />
        <CompetitionLink
          href={`/teams/${team.franchise_id}`}
          className="truncate underline-offset-4 hover:text-foreground hover:underline"
        >
          {team.name}
        </CompetitionLink>
      </span>
      <span className="font-mono text-5xl font-semibold tracking-tight tabular-nums">{wins}</span>
      <span className="text-xs text-muted-foreground">{wins === 1 ? "win" : "wins"}</span>
    </div>
  );
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-4">
        {side(h2h.a, r.a_won, COMPARE_SERIES.a.color, "left")}
        <span className="pb-6 text-sm text-muted-foreground">v</span>
        {side(h2h.b, r.b_won, COMPARE_SERIES.b.color, "right")}
      </div>
      <TallyBar record={r} />
      <p className="text-sm text-muted-foreground">
        {r.played} {r.played === 1 ? "meeting" : "meetings"}
        {r.no_result > 0 && `, ${r.no_result} without a result`}
        {r.tied > 0 && `, ${r.tied} settled by a super over`}.
      </p>
    </div>
  );
}

function TallyBar({ record }: { record: H2HRecord }) {
  const total = record.a_won + record.b_won;
  if (!total) return null;
  return (
    <span aria-hidden="true" className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
      <span
        style={{ width: `${(100 * record.a_won) / total}%`, background: COMPARE_SERIES.a.color }}
      />
      <span className="w-0.5 bg-card" />
      <span
        style={{ width: `${(100 * record.b_won) / total}%`, background: COMPARE_SERIES.b.color }}
      />
    </span>
  );
}

function SeasonStrip({ h2h }: { h2h: HeadToHead }) {
  const dot = (color: string | null, key: string) => (
    <span
      key={key}
      aria-hidden="true"
      className={cn("size-3 rounded-sm", color === null && "border border-border")}
      style={color ? { background: color } : undefined}
    />
  );
  return (
    <ol className="flex flex-col divide-y divide-border">
      {[...h2h.seasons].reverse().map((s) => (
        <li key={s.season} className="flex items-center gap-3 py-1.5">
          <span className="w-10 font-mono text-xs text-muted-foreground tabular-nums">
            {s.season}
          </span>
          <span className="flex flex-wrap gap-1">
            {Array.from({ length: s.record.a_won }, (_, i) => dot(COMPARE_SERIES.a.color, `a${i}`))}
            {Array.from({ length: s.record.b_won }, (_, i) => dot(COMPARE_SERIES.b.color, `b${i}`))}
            {Array.from({ length: s.record.no_result }, (_, i) => dot(null, `n${i}`))}
          </span>
          <span className="ml-auto font-mono text-xs tabular-nums">
            {s.record.a_won}–{s.record.b_won}
            {s.record.no_result > 0 && (
              <span className="text-muted-foreground"> · {s.record.no_result} NR</span>
            )}
            <span className="sr-only">
              {" "}
              ({h2h.a.franchise_id} {s.record.a_won}, {h2h.b.franchise_id} {s.record.b_won})
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function SplitTable({ h2h }: { h2h: HeadToHead }) {
  const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
  const td = "px-2 py-2.5 text-right font-mono tabular-nums";
  return (
    <div className="overflow-x-auto" {...scrollRegion("Head to head by situation")}>
      <table className="w-full min-w-[24rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Situation
            </th>
            <th scope="col" className={th}>
              Played
            </th>
            <th scope="col" className={th}>
              {h2h.a.franchise_id} won
            </th>
            <th scope="col" className={th}>
              {h2h.b.franchise_id} won
            </th>
            <th scope="col" className={cn(th, "w-28")}>
              <span className="sr-only">Share</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {h2h.splits.map((s) => (
            <tr key={s.key}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                {s.label}
              </th>
              <td className={td}>{s.record.played}</td>
              <td className={td}>{s.record.a_won}</td>
              <td className={td}>{s.record.b_won}</td>
              <td className="px-2 py-2.5">
                <TallyBar record={s.record} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Expectation({ h2h }: { h2h: HeadToHead }) {
  const e = h2h.expectation;
  if (!e) return null;
  const a = h2h.a.franchise_id;
  const b = h2h.b.franchise_id;
  const scale = (v: number) => `${(100 * v) / e.decided}%`;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm leading-relaxed">
        {a} won <span className="font-mono font-semibold tabular-nums">{e.a_won}</span> of{" "}
        {e.decided} decided meetings. Going by each side&rsquo;s form before each match, {a} would
        have been expected to win{" "}
        <span className="font-mono font-semibold tabular-nums">{e.a_expected.toFixed(1)}</span>, and
        chance alone puts the tally anywhere from{" "}
        <span className="font-mono tabular-nums">{e.low.toFixed(1)}</span> to{" "}
        <span className="font-mono tabular-nums">{e.high.toFixed(1)}</span> nine times in ten.
      </p>
      <div aria-hidden="true" className="relative h-8">
        <span className="absolute inset-x-0 top-1/2 h-px bg-border" />
        <span
          className="absolute top-1/2 h-3 -translate-y-1/2 rounded-full bg-muted-foreground/25"
          style={{ left: scale(e.low), width: `calc(${scale(e.high)} - ${scale(e.low)})` }}
        />
        <span
          className="absolute top-1/2 h-5 w-0.5 -translate-y-1/2 bg-muted-foreground"
          style={{ left: scale(e.a_expected) }}
        />
        <span
          className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
          style={{ left: scale(e.a_won), background: COMPARE_SERIES.a.color }}
        />
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="size-2.5 rounded-full"
            style={{ background: COMPARE_SERIES.a.color }}
          />
          {a}&rsquo;s wins
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-3 w-0.5 bg-muted-foreground" />
          Expected from form
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2 w-4 rounded-full bg-muted-foreground/25" />
          Range of chance
        </span>
      </p>
      <p className="rounded-xl bg-muted/40 p-3 text-sm">{expectationVerdict(e, a, b)}</p>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Form is a side&rsquo;s results in its previous 14 matches, pulled strongly toward an even
        record, because T20 results are noisy: even the side in better form wins only about 53% of
        the time in the IPL. Across every IPL rivalry, past head-to-head records add nothing to
        that. See{" "}
        <Link href="/ipl/lab/rivalries" className="text-primary underline-offset-4 hover:underline">
          Do rivalries and close finishes repeat?
        </Link>
      </p>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
      {children}
    </p>
  );
}

function Suggestions({
  competition,
  teams,
}: {
  competition: CompetitionId;
  teams: TeamsOverview["franchises"];
}) {
  const byId = new Map(teams.map((t) => [t.franchise_id, t]));
  // Without a list, the sides that have played most, in pairs.
  const busiest = [...teams]
    .filter((t) => t.is_active)
    .sort((x, y) => y.record.played - x.record.played)
    .slice(0, 6)
    .map((t) => t.franchise_id);
  const pairs = SUGGESTIONS[competition] ?? [
    [busiest[0], busiest[1]],
    [busiest[2], busiest[3]],
    [busiest[4], busiest[5]],
  ];
  return (
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {pairs
        .filter(([a, b]) => a && b && byId.has(a) && byId.has(b))
        .map(([a, b]) => (
          <li key={`${a}-${b}`}>
            <CompetitionLink
              href={h2hHref(a, b)}
              className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:border-primary/40 hover:bg-card"
            >
              <TeamSwatch color={byId.get(a)!.color} />
              <span className="font-mono">{a}</span>
              <span className="text-muted-foreground">v</span>
              <TeamSwatch color={byId.get(b)!.color} />
              <span className="font-mono">{b}</span>
            </CompetitionLink>
          </li>
        ))}
    </ul>
  );
}

export default async function HeadToHeadPage({
  params,
  searchParams,
}: PageProps<"/[competition]/teams/h2h">) {
  const competition = (await params).competition as CompetitionId;
  const raw = await searchParams;
  const a = parseTeamId(raw.a);
  const b = parseTeamId(raw.b);
  const from = parseSeason(raw.from);
  const to = parseSeason(raw.to);
  const overview = await getTeams(competition);
  const teams = overview.franchises;
  const options = teams.map((t) => ({ id: t.franchise_id, name: t.name, active: t.is_active }));
  const h2h = a && b && a !== b ? await load(competition, a, b, from, to) : null;
  const ta = teams.find((t) => t.franchise_id === a);
  const tb = teams.find((t) => t.franchise_id === b);
  // The seasons both franchises existed.
  const shared: [number, number] | null =
    ta && tb
      ? [Math.max(ta.first_season, tb.first_season), Math.min(ta.last_season, tb.last_season)]
      : null;

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <CompetitionLink href="/teams" className="hover:text-foreground">
          Teams
        </CompetitionLink>
        <span aria-hidden="true"> / </span>
        <span className="text-foreground">Head to head</span>
      </nav>
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Head to head</h1>
        <p className="max-w-3xl text-muted-foreground">
          Any two franchises&rsquo; record against each other, and whether it says more than each
          side&rsquo;s form at the time.
        </p>
      </header>

      <TeamPicker teams={options} a={a} b={b} />

      {!a || !b ? (
        <Panel id="suggestions" title="Pick two teams" lede="Or start with a classic.">
          <Suggestions competition={competition} teams={teams} />
        </Panel>
      ) : a === b ? (
        <Empty>Choose two different teams.</Empty>
      ) : !h2h ? (
        <Empty>One of these teams is not in the data.</Empty>
      ) : h2h.record.played === 0 ? (
        <Empty>
          {h2h.a.name} and {h2h.b.name} never met
          {shared && shared[0] <= shared[1]
            ? ` in ${seasonSpan(h2h.window.first, h2h.window.last, competition)}`
            : ""}
          .
        </Empty>
      ) : (
        <>
          {shared && shared[0] < shared[1] && (
            <SeasonWindow
              career={shared}
              first={Math.max(h2h.window.first, shared[0])}
              last={Math.min(h2h.window.last, shared[1])}
              allLabel="All meetings"
            />
          )}
          <div className="grid gap-6 xl:grid-cols-2">
            <Panel id="record" title="The record">
              <Tally h2h={h2h} />
            </Panel>
            <Panel id="expected" title="More than form?">
              <Expectation h2h={h2h} />
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel id="situations" title="By ground, batting order and stage">
              <SplitTable h2h={h2h} />
            </Panel>
            <Panel id="seasons" title="Season by season">
              <SeasonStrip h2h={h2h} />
            </Panel>
          </div>

          <Panel
            id="scoring"
            title="Runs in this rivalry"
            lede={[
              h2h.scoring.a_avg_total !== null && h2h.scoring.a_avg_total !== undefined
                ? `${h2h.a.franchise_id} averaged ${h2h.scoring.a_avg_total.toFixed(1)} batting first`
                : null,
              h2h.scoring.b_avg_total !== null && h2h.scoring.b_avg_total !== undefined
                ? `${h2h.b.franchise_id} ${h2h.scoring.b_avg_total.toFixed(1)}`
                : null,
            ]
              .filter(Boolean)
              .join("; ")
              .concat(" (full-length innings).")}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <TotalLine
                label={`${h2h.a.franchise_id}'s highest total`}
                total={h2h.scoring.a_highest}
              />
              <TotalLine
                label={`${h2h.b.franchise_id}'s highest total`}
                total={h2h.scoring.b_highest}
              />
            </div>
          </Panel>

          <Panel
            id="players"
            title="Who decided it"
            lede="Most runs and wickets in these meetings, for each side."
          >
            <div className="grid gap-6 md:grid-cols-2">
              <PlayerList
                title="Most runs"
                rows={[...h2h.batters]
                  .sort((x, y) => (y.runs ?? 0) - (x.runs ?? 0))
                  .map((p) => ({
                    id: p.player_id,
                    name: p.name,
                    main: String(p.runs ?? 0),
                    detail: (
                      <>
                        <span className="font-mono">{p.team.franchise_id}</span> · {p.innings} inns
                        · SR {rate(p.strike_rate, 1)}
                      </>
                    ),
                  }))}
              />
              <PlayerList
                title="Most wickets"
                rows={[...h2h.bowlers]
                  .sort((x, y) => (y.wickets ?? 0) - (x.wickets ?? 0))
                  .map((p) => ({
                    id: p.player_id,
                    name: p.name,
                    main: String(p.wickets ?? 0),
                    detail: (
                      <>
                        <span className="font-mono">{p.team.franchise_id}</span> · {p.innings} inns
                        · econ {rate(p.economy)}
                      </>
                    ),
                  }))}
              />
            </div>
          </Panel>

          <Panel id="meetings" title="Every meeting" lede="Newest first. Each opens the replay.">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {h2h.meetings.map((m) => (
                <MatchCard key={m.match_id} competition={competition} match={m} />
              ))}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
