import { CalendarDays, Flag, GitCompareArrows, Hand } from "lucide-react";
import Link from "next/link";

import { TeamBadge } from "@/components/match/team-badge";
import { MatchupTable } from "@/components/matchups/matchup-table";
import { FormChart, SeasonCharts } from "@/components/players/player-charts";
import {
  BattingPhaseTable,
  BowlingPhaseTable,
  DismissalBars,
  Panel,
  ParDelta,
  RecentBattingTable,
  RecentBowlingTable,
  StatTile,
  WpaNote,
} from "@/components/players/profile-parts";
import { RatingBars } from "@/components/players/ratings";
import { SimilarPlayers } from "@/components/players/similar-players";
import { BattingSplits, BowlingSplits } from "@/components/players/splits-table";
import { Badge } from "@/components/ui/badge";
import type {
  MatchupList,
  PlayerProfile,
  PlayerSplits,
  SimilarPlayers as Similar,
} from "@/lib/api/types";
import { compareHref } from "@/lib/compare";
import { getCompetition, type CompetitionId } from "@/lib/competitions";
import { formatDate } from "@/lib/format";
import {
  figures,
  formatWpa,
  handLabel,
  rate,
  roleLabel,
  seasonRanges,
  signed,
} from "@/lib/players";
import { CompetitionLink } from "@/components/competition/competition-link";
import { SeasonLabel } from "@/components/competition/season-label";

export function PlayerHeader({
  profile,
  competition,
}: {
  profile: PlayerProfile;
  competition: CompetitionId;
}) {
  const p = profile.player;
  const hand = handLabel(p.batting_hand);
  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {p.full_name ?? p.name}
        </h1>
        {p.full_name && p.full_name !== p.name && (
          <p className="font-mono text-sm text-muted-foreground">{p.name} on scorecards</p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
        <Badge variant="outline" className="text-primary">
          {roleLabel(p.role, p.is_keeper)}
        </Badge>
        <CompetitionLink
          href={compareHref(p.player_id, undefined)}
          className="inline-flex items-center gap-1.5 text-foreground underline-offset-4 hover:text-primary hover:underline"
        >
          <GitCompareArrows className="size-4" aria-hidden="true" />
          Compare
        </CompetitionLink>
        {p.country && (
          <span className="flex items-center gap-1.5">
            <Flag className="size-4" aria-hidden="true" />
            {p.country}
          </span>
        )}
        {(hand || p.bowling_style) && (
          <span className="flex items-center gap-1.5">
            <Hand className="size-4" aria-hidden="true" />
            {[hand, p.bowling_style].filter(Boolean).join(" · ")}
          </span>
        )}
        {p.date_of_birth && (
          <span className="flex items-center gap-1.5">
            <CalendarDays className="size-4" aria-hidden="true" />
            Born {formatDate(p.date_of_birth)}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-sm">
          <span className="font-mono tabular-nums">{p.matches}</span>{" "}
          <span className="text-muted-foreground">
            {getCompetition(competition).label} matches ·{" "}
            {p.first_season === p.last_season
              ? p.first_season
              : `${p.first_season}–${p.last_season}`}
          </span>
        </p>
        <ul className="flex flex-wrap gap-x-5 gap-y-2" aria-label="Teams">
          {p.teams.map((t) => (
            <li key={t.franchise_id} className="flex items-center gap-2 text-sm">
              <TeamBadge shortName={t.franchise_id} color={t.color} />
              <span className="text-muted-foreground" title={t.name}>
                {seasonRanges(t.seasons)} · {t.matches} {t.matches === 1 ? "match" : "matches"}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </header>
  );
}

function OpponentsPanel({
  profile,
  matchups,
  role,
}: {
  profile: PlayerProfile;
  matchups: MatchupList;
  role: "batting" | "bowling";
}) {
  const id = profile.player.player_id;
  const href = `/matchups?${role === "batting" ? "batter" : "bowler"}=${id}`;
  return (
    <Panel
      id={`${role}-opponents`}
      title={role === "batting" ? "Most-faced bowlers" : "Most-faced batters"}
      lede={
        <>
          Head-to-head records with at least 12 balls, next to what each player&apos;s overall
          record predicts and a sample-size-aware estimate.{" "}
          <Link href={href} className="text-foreground underline-offset-4 hover:underline">
            All matchups in the Matchup Lab
          </Link>
          .
        </>
      }
    >
      <MatchupTable items={matchups.items} show={role === "batting" ? "bowler" : "batter"} />
    </Panel>
  );
}

function FieldingPanel({ profile, idPrefix }: { profile: PlayerProfile; idPrefix: string }) {
  const items = [
    ["Catches", profile.fielding.catches],
    ["Stumpings", profile.fielding.stumpings],
    ["Run outs", profile.fielding.run_outs],
  ] as const;
  return (
    <Panel id={`${idPrefix}-fielding`} title="In the field">
      <dl className="grid grid-cols-3 gap-3 text-center">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-xl bg-muted/40 px-2 py-3">
            <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</dt>
            <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function SimilarPanel({
  profile,
  similar,
  role,
}: {
  profile: PlayerProfile;
  similar?: Similar | null;
  role: "batting" | "bowling";
}) {
  const group = similar?.[role];
  if (!group || group.items.length === 0) return null;
  const { first_season: debut, last_season: latest } = profile.player;
  const window = {
    from: profile.window.first > debut ? profile.window.first : undefined,
    to: profile.window.last < latest ? profile.window.last : undefined,
  };
  return (
    <Panel
      id={`${role}-similar`}
      title={role === "batting" ? "Similar batters" : "Similar bowlers"}
      lede="Closest playing styles over the same seasons."
    >
      <SimilarPlayers
        group={group}
        playerId={profile.player.player_id}
        role={role}
        window={window}
      />
    </Panel>
  );
}

function windowLabel(profile: PlayerProfile): string {
  const first = Math.max(profile.window.first, profile.player.first_season);
  const last = Math.min(profile.window.last, profile.player.last_season);
  return first === last ? String(first) : `${first}–${last}`;
}

export function BattingView({
  profile,
  splits,
  matchups,
  similar,
}: {
  profile: PlayerProfile;
  splits: PlayerSplits;
  matchups?: MatchupList | null;
  similar?: Similar | null;
}) {
  const b = profile.batting!;
  const window = windowLabel(profile);
  const recent = profile.recent.batting;
  const last10 = recent.slice(0, 10);
  const recentRuns = last10.reduce((s, i) => s + i.runs, 0);
  const recentBalls = last10.reduce((s, i) => s + i.balls, 0);
  const recentOuts = last10.filter((i) => i.is_out).length;
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatTile label="Runs" value={b.runs.toLocaleString("en-IN")}>
          {b.innings} innings · {b.not_outs} not out · {b.balls.toLocaleString("en-IN")} balls
        </StatTile>
        <StatTile label="Average" value={rate(b.average)}>
          Par {rate(b.par_average)} for the same balls ·{" "}
          <ParDelta
            delta={b.average !== null && b.par_average ? b.average - b.par_average : null}
          />
        </StatTile>
        <StatTile label="Strike rate" value={rate(b.strike_rate)}>
          Par {rate(b.par_strike_rate)} ·{" "}
          <ParDelta
            delta={
              b.strike_rate !== null && b.par_strike_rate !== null
                ? b.strike_rate - b.par_strike_rate
                : null
            }
          />
        </StatTile>
        <StatTile label="Runs above par" value={signed(b.runs_above_par, 0)}>
          Runs scored beyond what an average batter would have made from the same balls.
        </StatTile>
        <StatTile label="50s / 100s" value={`${b.fifties} / ${b.hundreds}`}>
          {b.highest ? (
            <>
              {`Highest ${b.highest.runs}${b.highest.not_out ? "*" : ""} vs ${b.highest.opposition_id}, `}
              <SeasonLabel season={b.highest.season} />
            </>
          ) : (
            "No innings yet"
          )}
          {b.ducks > 0 && ` · ${b.ducks} ${b.ducks === 1 ? "duck" : "ducks"}`}
        </StatTile>
        <StatTile label="Win probability added" value={formatWpa(b.wpa)}>
          {b.wpa === null || b.wpa === undefined ? (
            "Not available for these seasons."
          ) : (
            <WpaNote wpa={b.wpa} innings={b.wpa_innings} />
          )}
        </StatTile>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {profile.ratings?.batting && (
          <Panel
            id="batting-ratings"
            title="CricIQ Ratings"
            lede={`Batting against qualified batters in ${window}, measured against par and adjusted for sample size.`}
          >
            <RatingBars group={profile.ratings?.batting} noun="batters" window={window} />
          </Panel>
        )}
        <div className="flex min-w-0 flex-col gap-6">
          <Panel
            id="batting-phases"
            title="By phase"
            lede="Where the runs come from, and how each phase compares with par."
          >
            <BattingPhaseTable rows={profile.phases.batting} />
          </Panel>
          <SimilarPanel profile={profile} similar={similar} role="batting" />
        </div>
      </div>

      <Panel
        id="batting-seasons"
        title="Season by season"
        lede="Totals each season, and the strike rate against the par for that season's balls, so rising league scoring does not flatter later years."
      >
        <SeasonCharts seasons={profile.seasons} role="batting" />
      </Panel>

      {matchups && matchups.items.length > 0 && (
        <OpponentsPanel profile={profile} matchups={matchups} role="batting" />
      )}

      {splits.batting.length > 0 && (
        <Panel
          id="batting-splits"
          title="Splits"
          lede={`Batting in ${window}, split every way the data allows. "vs par" is strike rate minus par for the same balls. Rows under 60 balls are flagged as small samples.`}
        >
          <BattingSplits groups={splits.batting} />
        </Panel>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {recent.length > 0 && (
          <Panel
            id="batting-form"
            title="Recent form"
            lede={
              <>
                Last {last10.length} innings:{" "}
                <span className="font-mono text-foreground tabular-nums">{recentRuns}</span> runs at
                a strike rate of{" "}
                <span className="font-mono text-foreground tabular-nums">
                  {recentBalls ? ((100 * recentRuns) / recentBalls).toFixed(1) : "—"}
                </span>
                {recentOuts > 0 && (
                  <>
                    , average{" "}
                    <span className="font-mono text-foreground tabular-nums">
                      {(recentRuns / recentOuts).toFixed(1)}
                    </span>
                  </>
                )}
                .
              </>
            }
          >
            <div className="flex flex-col gap-6">
              <FormChart innings={recent} />
              <RecentBattingTable innings={last10} />
            </div>
          </Panel>
        )}
        <div className="flex flex-col gap-6">
          <Panel id="batting-dismissals" title="How out">
            <DismissalBars rows={profile.dismissals.batting} total={b.outs} />
          </Panel>
          <FieldingPanel profile={profile} idPrefix="batting" />
        </div>
      </div>
    </div>
  );
}

export function BowlingView({
  profile,
  splits,
  matchups,
  similar,
}: {
  profile: PlayerProfile;
  splits: PlayerSplits;
  matchups?: MatchupList | null;
  similar?: Similar | null;
}) {
  const b = profile.bowling!;
  const window = windowLabel(profile);
  const recent = profile.recent.bowling.slice(0, 10);
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatTile label="Wickets" value={b.wickets}>
          {b.innings} innings · {b.overs} overs
          {b.maidens > 0 && ` · ${b.maidens} ${b.maidens === 1 ? "maiden" : "maidens"}`}
        </StatTile>
        <StatTile label="Economy" value={rate(b.economy)}>
          Par {rate(b.par_economy)} for the same balls ·{" "}
          <ParDelta
            delta={b.economy !== null && b.par_economy !== null ? b.economy - b.par_economy : null}
            higherIsBetter={false}
            digits={2}
          />
        </StatTile>
        <StatTile label="Strike rate" value={rate(b.strike_rate, 1)}>
          Balls per wicket · par {rate(b.par_strike_rate, 1)}
          {b.strike_rate !== null && b.par_strike_rate !== null && (
            <>
              {" · "}
              <ParDelta delta={b.strike_rate - b.par_strike_rate} higherIsBetter={false} />
            </>
          )}
        </StatTile>
        <StatTile label="Runs saved vs par" value={signed(b.runs_saved, 0)}>
          Runs an average bowler would have conceded from the same balls, minus the runs conceded.
        </StatTile>
        <StatTile label="Best" value={b.best ? figures(b.best.wickets, b.best.runs) : "—"}>
          {b.best && (
            <>
              {`vs ${b.best.opposition_id}, `}
              <SeasonLabel season={b.best.season} />
            </>
          )}
          {` · average ${rate(b.average, 1)}`}
          {(b.four_wickets > 0 || b.five_wickets > 0) &&
            ` · ${b.four_wickets} four-fors, ${b.five_wickets} five-fors`}
        </StatTile>
        <StatTile label="Win probability added" value={formatWpa(b.wpa)}>
          {b.wpa === null || b.wpa === undefined ? (
            "Not available for these seasons."
          ) : (
            <WpaNote wpa={b.wpa} innings={b.wpa_innings} />
          )}
        </StatTile>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {profile.ratings?.bowling && (
          <Panel
            id="bowling-ratings"
            title="CricIQ Ratings"
            lede={`Bowling against qualified bowlers in ${window}, measured against par and adjusted for sample size.`}
          >
            <RatingBars group={profile.ratings?.bowling} noun="bowlers" window={window} />
          </Panel>
        )}
        <div className="flex min-w-0 flex-col gap-6">
          <Panel
            id="bowling-phases"
            title="By phase"
            lede="When the overs are bowled, and the economy against par for each phase."
          >
            <BowlingPhaseTable rows={profile.phases.bowling} />
          </Panel>
          <SimilarPanel profile={profile} similar={similar} role="bowling" />
        </div>
      </div>

      <Panel
        id="bowling-seasons"
        title="Season by season"
        lede="Wickets each season, and economy against the par for that season's balls."
      >
        <SeasonCharts seasons={profile.seasons} role="bowling" />
      </Panel>

      {matchups && matchups.items.length > 0 && (
        <OpponentsPanel profile={profile} matchups={matchups} role="bowling" />
      )}

      {splits.bowling.length > 0 && (
        <Panel
          id="bowling-splits"
          title="Splits"
          lede={`Bowling in ${window}, split every way the data allows. "vs par" is economy minus par; negative is better. Rows under 60 balls are flagged as small samples.`}
        >
          <BowlingSplits groups={splits.bowling} />
        </Panel>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {recent.length > 0 && (
          <Panel id="bowling-form" title="Recent form" lede={`Last ${recent.length} innings.`}>
            <RecentBowlingTable innings={recent} />
          </Panel>
        )}
        <div className="flex flex-col gap-6">
          <Panel id="bowling-dismissals" title="How the wickets came">
            <DismissalBars rows={profile.dismissals.bowling} total={b.wickets} />
          </Panel>
          <FieldingPanel profile={profile} idPrefix="bowling" />
        </div>
      </div>
    </div>
  );
}
