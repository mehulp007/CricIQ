import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { CompareSelector } from "@/components/compare/compare-selector";
import { RatingComparison } from "@/components/compare/rating-comparison";
import { TrendChart } from "@/components/compare/trend-chart";
import { TeamBadge } from "@/components/match/team-badge";
import type { PickedPlayer } from "@/components/matchups/player-picker";
import { Panel } from "@/components/players/profile-parts";
import { SeasonWindow } from "@/components/players/season-window";
import { ApiError, getMatchup, getPlayer } from "@/lib/api/client";
import type { MatchupDetail, PlayerProfile } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import {
  COMPARE_SERIES,
  type CompareRole,
  type CompareState,
  compareHref,
  compareRoles,
  headlineRows,
  parseCompare,
} from "@/lib/compare";
import { rate, roleLabel, signed } from "@/lib/players";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Compare players",
  description:
    "Compare any two IPL players over the same seasons: numbers against par, CricIQ Ratings with intervals, season-by-season form by year or by age, phases and their head-to-head.",
};

const SUGGESTIONS: { a: [string, string]; b: [string, string]; role: CompareRole; why: string }[] =
  [
    {
      a: ["ba607b88", "Virat Kohli"],
      b: ["740742ef", "Rohit Sharma"],
      role: "batting",
      why: "India's two great IPL openers",
    },
    {
      a: ["462411b3", "Jasprit Bumrah"],
      b: ["a12e1d51", "Lasith Malinga"],
      role: "bowling",
      why: "Mumbai's death-overs pair, a decade apart",
    },
    {
      a: ["9d430b40", "Sunil Narine"],
      b: ["5f547c8b", "Rashid Khan"],
      role: "bowling",
      why: "The two most miserly spinners",
    },
    {
      a: ["db584dad", "Chris Gayle"],
      b: ["c4487b84", "AB de Villiers"],
      role: "batting",
      why: "Royal Challengers' big hitters",
    },
  ];

async function load(id: string | undefined, state: CompareState): Promise<PlayerProfile | null> {
  if (!id) return null;
  try {
    return await getPlayer(id, { from: state.from, to: state.to });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) return null;
    throw error;
  }
}

/** A head-to-head record, if the two ever met with these roles (optional extra). */
async function meeting(batter: string, bowler: string, state: CompareState) {
  try {
    const detail = await getMatchup(batter, bowler, { from: state.from, to: state.to });
    return detail.head_to_head.balls > 0 ? detail : null;
  } catch {
    return null;
  }
}

function picked(profile: PlayerProfile | null): PickedPlayer | null {
  return profile
    ? { player_id: profile.player.player_id, name: profile.player.full_name ?? profile.player.name }
    : null;
}

function displayName(profile: PlayerProfile): string {
  return profile.player.full_name ?? profile.player.name;
}

function PlayerCard({ profile, color }: { profile: PlayerProfile; color: string }) {
  const p = profile.player;
  const team = p.teams[0];
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-2xl border border-border bg-card/70 p-4 sm:p-5">
      <span aria-hidden="true" className="h-1 w-10 rounded-full" style={{ background: color }} />
      <Link
        href={`/players/${p.player_id}`}
        className="truncate text-lg font-semibold tracking-tight underline-offset-4 hover:text-primary hover:underline"
      >
        {displayName(profile)}
      </Link>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>{roleLabel(p.role, p.is_keeper)}</span>
        {team && <TeamBadge shortName={team.franchise_id} color={team.color} />}
        <span>
          {p.matches} matches · {p.first_season}–{p.last_season}
        </span>
      </p>
    </div>
  );
}

function RoleLinks({
  roles,
  role,
  state,
}: {
  roles: CompareRole[];
  role: CompareRole;
  state: CompareState;
}) {
  if (roles.length < 2) return null;
  return (
    <nav aria-label="Compare as" className="flex gap-1.5">
      {roles.map((r) => (
        <Link
          key={r}
          href={compareHref(state.a, state.b, { ...state, role: r })}
          aria-current={r === role ? "page" : undefined}
          scroll={false}
          className={cn(
            "inline-flex h-8 items-center rounded-lg border px-3 text-xs transition-colors",
            r === role
              ? "border-primary/50 bg-primary/10 text-foreground"
              : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          {r === "batting" ? "Batting" : "Bowling"}
        </Link>
      ))}
    </nav>
  );
}

function NameHeads({ names }: { names: [string, string] }) {
  return names.map((name, i) => (
    <th key={name} scope="col" className="px-3 py-2 text-right text-xs font-medium">
      <span className="inline-flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="size-2 rounded-full"
          style={{ background: i === 0 ? COMPARE_SERIES.a.color : COMPARE_SERIES.b.color }}
        />
        {name}
      </span>
    </th>
  ));
}

function HeadlineTable({
  a,
  b,
  role,
  names,
}: {
  a: PlayerProfile;
  b: PlayerProfile;
  role: CompareRole;
  names: [string, string];
}) {
  const rows = headlineRows(a, b, role);
  const cell = "px-3 py-2.5 text-right font-mono tabular-nums";
  return (
    <div className="relative overflow-x-auto" {...scrollRegion("Side by side")}>
      <table className="w-full min-w-[26rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th
              scope="col"
              className="px-3 py-2 text-left text-xs font-medium text-muted-foreground"
            >
              <span className="sr-only">Measure</span>
            </th>
            <NameHeads names={names} />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className="px-3 py-2.5 text-left font-normal" title={r.hint}>
                {r.label}
              </th>
              {(["a", "b"] as const).map((side) => (
                <td
                  key={side}
                  className={cn(
                    cell,
                    r.better === side ? "font-semibold text-foreground" : "text-muted-foreground",
                  )}
                >
                  {r[side]}
                  {r.better === side && <span className="sr-only"> (better)</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PhaseTable({
  a,
  b,
  role,
  names,
}: {
  a: PlayerProfile;
  b: PlayerProfile;
  role: CompareRole;
  names: [string, string];
}) {
  const batting = role === "batting";
  const phases = (batting ? a.phases.batting : a.phases.bowling).map((p) => p.phase);
  for (const p of batting ? b.phases.batting : b.phases.bowling) {
    if (!phases.includes(p.phase)) phases.push(p.phase);
  }
  const find = (profile: PlayerProfile, phase: string) =>
    (batting ? profile.phases.batting : profile.phases.bowling).find((p) => p.phase === phase);
  const label = (phase: string) => (find(a, phase) ?? find(b, phase))!.label;
  const value = (profile: PlayerProfile, phase: string): ReactNode => {
    if (batting) {
      const r = profile.phases.batting.find((p) => p.phase === phase);
      if (!r || r.strike_rate === null || r.strike_rate === undefined) return "—";
      const delta =
        r.par_strike_rate === null || r.par_strike_rate === undefined
          ? null
          : r.strike_rate - r.par_strike_rate;
      return (
        <>
          {rate(r.strike_rate, 1)}
          <span className="text-muted-foreground"> ({delta === null ? "—" : signed(delta)})</span>
          <span className="block text-[11px] text-muted-foreground">{r.balls} balls</span>
        </>
      );
    }
    const r = profile.phases.bowling.find((p) => p.phase === phase);
    if (!r || r.economy === null || r.economy === undefined) return "—";
    const saved =
      r.par_economy === null || r.par_economy === undefined ? null : r.par_economy - r.economy;
    return (
      <>
        {rate(r.economy)}
        <span className="text-muted-foreground"> ({saved === null ? "—" : signed(saved, 2)})</span>
        <span className="block text-[11px] text-muted-foreground">
          {Math.floor(r.balls / 6)}.{r.balls % 6} overs · {r.wickets} wkts
        </span>
      </>
    );
  };
  return (
    <div className="overflow-x-auto" {...scrollRegion("By phase")}>
      <table className="w-full min-w-[26rem] text-sm">
        <thead className="border-b border-border">
          <tr>
            <th
              scope="col"
              className="px-3 py-2 text-left text-xs font-medium text-muted-foreground"
            >
              Phase
            </th>
            <NameHeads names={names} />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {phases.map((phase) => (
            <tr key={phase}>
              <th scope="row" className="px-3 py-2.5 text-left font-normal">
                {label(phase)}
              </th>
              <td className="px-3 py-2.5 text-right font-mono tabular-nums">{value(a, phase)}</td>
              <td className="px-3 py-2.5 text-right font-mono tabular-nums">{value(b, phase)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Meeting({ detail }: { detail: MatchupDetail }) {
  const h = detail.head_to_head;
  const batter = detail.batter.full_name ?? detail.batter.name;
  const bowler = detail.bowler.full_name ?? detail.bowler.name;
  const params = new URLSearchParams({
    batter: detail.batter.player_id,
    bowler: detail.bowler.player_id,
  });
  return (
    <li className="flex flex-col gap-1 rounded-xl bg-muted/40 p-4">
      <p className="text-sm">
        <span className="font-medium">{batter}</span>
        <span className="text-muted-foreground"> batting against </span>
        <span className="font-medium">{bowler}</span>
      </p>
      <p className="font-mono text-sm tabular-nums">
        {h.runs} runs off {h.balls} balls, {h.dismissals}{" "}
        {h.dismissals === 1 ? "dismissal" : "dismissals"}
        <span className="text-muted-foreground">
          {" "}
          · strike rate {h.balls ? ((100 * h.runs) / h.balls).toFixed(1) : "—"}
        </span>
      </p>
      <Link
        href={`/matchups?${params}`}
        className="text-xs text-primary underline-offset-4 hover:underline"
      >
        Read it in the Matchup Lab
      </Link>
    </li>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
      {children}
    </p>
  );
}

function Suggestions() {
  return (
    <section aria-labelledby="suggestions" className="flex flex-col gap-4">
      <h2 id="suggestions" className="text-lg font-semibold tracking-tight">
        Try a classic
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <li key={s.a[0] + s.b[0]}>
            <Link
              href={compareHref(s.a[0], s.b[0], { role: s.role })}
              className="flex h-full flex-col gap-1 rounded-2xl border border-border bg-card/70 p-4 transition-colors hover:border-primary/40 hover:bg-card"
            >
              <span className="font-medium">
                {s.a[1]} <span className="text-muted-foreground">vs</span> {s.b[1]}
              </span>
              <span className="text-sm text-muted-foreground">{s.why}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

async function Comparison({
  a,
  b,
  state,
}: {
  a: PlayerProfile;
  b: PlayerProfile;
  state: CompareState;
}) {
  const names: [string, string] = [displayName(a), displayName(b)];
  const { roles, role } = compareRoles(a, b, state.role);
  const career: [number, number] = [
    Math.min(a.player.first_season, b.player.first_season),
    Math.max(a.player.last_season, b.player.last_season),
  ];
  const first = Math.max(a.window.first, career[0]);
  const last = Math.min(a.window.last, career[1]);
  const window = first === last ? String(first) : `${first}–${last}`;
  const [aBats, bBats] = await Promise.all([
    meeting(a.player.player_id, b.player.player_id, state),
    meeting(b.player.player_id, a.player.player_id, state),
  ]);
  const meetings = [aBats, bBats].filter((m): m is MatchupDetail => m !== null);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <PlayerCard profile={a} color={COMPARE_SERIES.a.color} />
        <PlayerCard profile={b} color={COMPARE_SERIES.b.color} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SeasonWindow career={career} first={first} last={last} />
        {role && <RoleLinks roles={roles} role={role} state={state} />}
      </div>

      {role === null ? (
        <Empty>
          {names[0]} and {names[1]} have no batting or bowling in common in {window}. Try other
          seasons.
        </Empty>
      ) : (
        <>
          <div className="grid gap-6 xl:grid-cols-2">
            <Panel
              id="compare-numbers"
              title={role === "batting" ? "Batting side by side" : "Bowling side by side"}
              lede={`${window}. Bold marks the better figure where one direction is better; par is what an average player would have done from the same balls.`}
            >
              <HeadlineTable a={a} b={b} role={role} names={names} />
            </Panel>
            <Panel
              id="compare-ratings"
              title="CricIQ Ratings"
              lede="Each player against qualified players in the same seasons, after allowing for sample size."
            >
              <RatingComparison
                a={a.ratings?.[role]}
                b={b.ratings?.[role]}
                names={names}
                noun={role === "batting" ? "batters" : "bowlers"}
              />
            </Panel>
          </div>

          <Panel
            id="compare-trend"
            title="Season by season"
            lede={
              role === "batting"
                ? "Runs above par per 100 balls each season: how much faster than an average batter on the same balls."
                : "Runs saved per over against par each season: how much cheaper than an average bowler on the same balls."
            }
          >
            <TrendChart a={a} b={b} role={role} names={names} />
          </Panel>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel
              id="compare-phases"
              title="By phase"
              lede={
                role === "batting"
                  ? "Strike rate in each phase, with the difference from par in brackets."
                  : "Economy in each phase, with runs saved per over against par in brackets."
              }
            >
              <PhaseTable a={a} b={b} role={role} names={names} />
            </Panel>
            <Panel
              id="compare-meetings"
              title="Head to head"
              lede="When one bowled to the other, in the same seasons."
            >
              {meetings.length ? (
                <ul className="flex flex-col gap-3">
                  {meetings.map((m) => (
                    <Meeting key={m.batter.player_id} detail={m} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {names[0]} and {names[1]} never faced each other in {window}.
                </p>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

export default async function ComparePage({ searchParams }: PageProps<"/compare">) {
  const state = parseCompare(await searchParams);
  const [a, b] = await Promise.all([load(state.a, state), load(state.b, state)]);

  let body: ReactNode;
  if (a && b && a.player.player_id === b.player.player_id) {
    body = <Empty>Pick two different players.</Empty>;
  } else if (a && b) {
    body = <Comparison a={a} b={b} state={state} />;
  } else if ((state.a && !a) || (state.b && !b)) {
    body = <Empty>One of these players could not be found.</Empty>;
  } else {
    body = <Suggestions />;
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Compare players</h1>
        <p className="max-w-3xl text-muted-foreground">
          Any two players over the same seasons, measured against par so different eras and roles
          compare fairly: their numbers, CricIQ Ratings with honest intervals, how their seasons
          went by year or by age, and how they fared against each other.
        </p>
      </header>
      <Panel id="pick" title="Pick two players">
        <CompareSelector a={picked(a)} b={picked(b)} />
      </Panel>
      {body}
    </div>
  );
}
