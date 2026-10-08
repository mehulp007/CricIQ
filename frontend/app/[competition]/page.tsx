import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  Calculator,
  GitCompareArrows,
  Play,
  Shield,
  Swords,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { MatchCard } from "@/components/match/match-card";
import { LatestMatches } from "@/components/matches/latest-matches";
import { LatestSeries } from "@/components/series/latest-series";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  competitionPath,
  getCompetition,
  isCompetitionId,
  isTest,
  phrase,
  type Competition,
  type CompetitionId,
} from "@/lib/competitions";
import { featuredMatches, seasonSnapshot, type SeasonSnapshot } from "@/lib/featured";
import { modelsFor, testModels } from "@/lib/models";
import { signed } from "@/lib/players";

export async function generateMetadata({ params }: PageProps<"/[competition]">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.name} analytics`,
    description: `${c.name} analytics, ball by ball: match replay with calibrated win probability and score projection, player profiles against par, and sample-size-aware batter vs bowler matchups.`,
  };
}

function capabilities(c: Competition): {
  icon: LucideIcon;
  title: string;
  body: string;
  path: string;
}[] {
  const team = c.teamType === "national" ? "side" : "franchise";
  const test = c.format === "Test";
  return [
    {
      icon: Activity,
      title: "Ball-by-ball replay",
      body: test
        ? `Relive any ${c.noun} delivery by delivery, day by day: the chances of a win, a draw and a defeat after every ball, every innings projected, the scorecard and the commentary.`
        : `Relive any ${c.noun} delivery by delivery: live scoreboard, scorecard, commentary, worm and Manhattan charts.`,
      path: "/matches",
    },
    ...(test
      ? [
          {
            icon: Calculator,
            title: "Chase calculator",
            body: "Set up a fourth-innings chase between any two sides and see the chances of a win, a draw and a defeat, and how they move with the target.",
            path: "/chase",
          },
        ]
      : []),
    {
      icon: Users,
      title: "Player Lab",
      body: `Every player's ${c.label} career measured against par, with CricIQ Ratings that allow for sample size, splits, win probability added, similar players and their record in every other competition.`,
      path: "/players",
    },
    {
      icon: GitCompareArrows,
      title: "Compare players",
      body: "Any two players over the same seasons: numbers against par, ratings with intervals, and their seasons lined up by year or by age.",
      path: "/compare",
    },
    {
      icon: Swords,
      title: "Matchup Lab",
      body: "Any batter against any bowler, read three ways so a few dozen balls of history are never over-read, plus next-ball odds.",
      path: "/matchups",
    },
    {
      icon: Shield,
      title: "Teams",
      body: `Every ${team}'s record by season, situation and opponent, and head to head against form.`,
      path: "/teams",
    },
    {
      icon: BrainCircuit,
      title: "Model Insights",
      body: "How each model was built and tested: calibration, backtests, rejected features and limitations.",
      path: "/models",
    },
  ];
}

// The overview's first call to action (by default the first featured replay).
const HERO_REPLAY: Partial<Record<CompetitionId, { matchId: number; label: string }>> = {
  ipl: { matchId: 1181768, label: "2019 final" },
  odi: { matchId: 1144530, label: "2019 World Cup final" },
  test: { matchId: 1152848, label: "Headingley 2019 Test" },
};

const LEADERS: { key: keyof SeasonSnapshot["leaders"]; label: string; unit: string }[] = [
  { key: "runs", label: "Most runs", unit: "runs" },
  { key: "wickets", label: "Most wickets", unit: "wickets" },
  { key: "runs_above_par", label: "Most runs above par", unit: "runs" },
  { key: "runs_saved", label: "Most runs saved vs par", unit: "runs" },
];

function SeasonSnapshotSection({ competition }: { competition: CompetitionId }) {
  const c = getCompetition(competition);
  const s = seasonSnapshot(competition);
  const change =
    s.previous_first_innings_average !== null
      ? s.first_innings_average - s.previous_first_innings_average
      : null;
  const title =
    c.teamType === "national" ? `${phrase(competition)} in ${s.label}` : `${c.label} ${s.label}`;
  return (
    <section aria-labelledby="season-heading" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="season-heading" className="text-xl font-semibold tracking-tight">
            {title} at a glance
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {s.matches} matches
            {s.champion && <> · champions {s.champion}</>}. Par adjusts for the season and phase, so
            the last two cards reward quality, not just volume.
          </p>
        </div>
        <Link
          href={competitionPath(competition, `/matches?season=${s.season}`)}
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          All {s.label} matches
        </Link>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <Card className="bg-card/70">
          <CardContent className="flex flex-col gap-2">
            <p className="text-[11px] tracking-wide text-muted-foreground uppercase">
              Average first-innings total
            </p>
            <p className="font-mono text-3xl font-semibold tracking-tight tabular-nums">
              {s.first_innings_average.toFixed(0)}
            </p>
            <p className="text-xs text-muted-foreground">
              {change !== null && <>{signed(change)} on the season before · </>}
              {s.sixes.toLocaleString("en-IN")} sixes this season
            </p>
          </CardContent>
        </Card>
        {LEADERS.map(({ key, label, unit }) => {
          const leader = s.leaders[key];
          return (
            <Card key={key} className="bg-card/70">
              <CardContent className="flex flex-col gap-2">
                <p className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</p>
                <p className="font-mono text-3xl font-semibold tracking-tight tabular-nums">
                  {leader.value.toFixed(0)}
                  <span className="ml-1.5 font-sans text-sm font-normal text-muted-foreground">
                    {unit}
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">
                  <Link
                    href={competitionPath(
                      competition,
                      `/players/${leader.player_id}?from=${s.season}&to=${s.season}`,
                    )}
                    className="font-medium text-foreground underline-offset-4 hover:text-primary hover:underline"
                  >
                    {leader.name}
                  </Link>
                  {leader.team && ` · ${leader.team}`} · {leader.detail}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

interface SwingCard {
  match_id: number;
  innings_no: number;
  seq_no: number;
  ball_label: string | null;
  season: number;
  stage?: string;
  teams: string;
  result: string;
  description: string;
  swing: number;
}

function BiggestSwings({ competition }: { competition: CompetitionId }) {
  const c = getCompetition(competition);
  const test = isTest(competition);
  const swings: SwingCard[] = (
    isTest(competition) ? testModels().winProbability.swings : modelsFor(competition).swings
  ).slice(0, 3);
  if (swings.length === 0) return null;
  return (
    <section aria-labelledby="swings-heading" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="swings-heading" className="text-xl font-semibold tracking-tight">
            The biggest swings in {c.label} history
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {test
              ? "Single balls that moved the expected result the most (a win counts 1, a draw a half). Open one to replay the moment."
              : "Single balls that moved the win probability the most. Open one to replay the moment."}
          </p>
        </div>
        <Link
          href={competitionPath(competition, "/models?tab=win-probability#swings-heading")}
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Top 10
        </Link>
      </div>
      <ul className="grid gap-4 md:grid-cols-3">
        {swings.map((s) => (
          <li key={`${s.match_id}-${s.seq_no}`} className="flex">
            <Link
              href={competitionPath(
                competition,
                `/matches/${s.match_id}?ball=${s.innings_no}.${s.seq_no}`,
              )}
              className="group flex w-full flex-col gap-2 rounded-2xl border border-border bg-card/70 p-5 transition-colors hover:border-primary/40"
            >
              <span className="flex items-center justify-between gap-2">
                <span className="font-mono text-2xl font-semibold text-positive tabular-nums">
                  +{s.swing.toFixed(0)} pts
                </span>
                <ArrowUpRight
                  className="size-4 text-muted-foreground group-hover:text-primary"
                  aria-hidden="true"
                />
              </span>
              <span className="text-sm font-medium group-hover:text-primary">{s.description}</span>
              <span className="text-xs leading-relaxed text-muted-foreground">
                {s.teams}, {s.season} {s.stage && s.stage !== "League" ? s.stage.toLowerCase() : ""}{" "}
                · {test ? `innings ${s.innings_no}, ` : ""}ball {s.ball_label} · {s.result}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default async function CompetitionOverviewPage({ params }: PageProps<"/[competition]">) {
  const competition = (await params).competition as CompetitionId;
  const c = getCompetition(competition);
  const featured = featuredMatches(competition);
  const lead = HERO_REPLAY[competition] ?? {
    matchId: featured[0]?.match_id,
    label: featured[0]?.headline.split(",")[0],
  };
  const prose =
    c.teamType === "national"
      ? `CricIQ turns every ${c.noun} delivery since ${c.firstSeason} into interactive analytics, from World Cup finals to associate qualifiers.`
      : `CricIQ turns every ${c.label} delivery since ${c.spansNewYear ? `${c.firstSeason - 1}/${String(c.firstSeason % 100).padStart(2, "0")}` : c.firstSeason} into interactive analytics.`;
  return (
    <div className="flex flex-col gap-14">
      <section className="glass relative overflow-hidden rounded-3xl px-6 py-12 sm:px-10 sm:py-16">
        <Badge variant="outline" className="mb-6 font-mono text-[11px] tracking-wide text-primary">
          {c.label} · {c.firstSeason} onward
        </Badge>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
          Decode the game.
          <span className="block text-muted-foreground">Predict the next move.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          {prose} Replay any match with{" "}
          {isTest(competition)
            ? "the chances of a win, a draw and a defeat after every ball"
            : "each side's chance of winning after every ball"}
          , explore and compare any player&apos;s career against par, and read any batter-vs-bowler
          rivalry without over-reading small samples. Every number comes from a tested model you can
          inspect.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {lead.matchId && (
            <Link
              href={competitionPath(competition, `/matches/${lead.matchId}`)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85"
            >
              <Play className="size-4" aria-hidden="true" />
              Replay the {lead.label}
            </Link>
          )}
          <Link
            href={competitionPath(competition, "/players")}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            <Users className="size-4" aria-hidden="true" />
            Explore players
          </Link>
          <Link
            href={competitionPath(competition, "/matchups")}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            <Swords className="size-4" aria-hidden="true" />
            Compare a batter and a bowler
          </Link>
        </div>
      </section>

      <Suspense fallback={null}>
        <LatestMatches competition={competition} />
      </Suspense>

      <Suspense fallback={null}>
        <LatestSeries competition={competition} />
      </Suspense>

      <section aria-labelledby="featured-heading" className="flex flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="featured-heading" className="text-xl font-semibold tracking-tight">
              Featured replays
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {competition === "ipl"
                ? "Iconic IPL matches, ready to replay ball by ball."
                : competition === "t20i"
                  ? "Every men's T20 World Cup final, ready to replay ball by ball."
                  : competition === "odi"
                    ? "Every men's World Cup final since 2003, the Champions Trophy finals and the highest chase, ready to replay ball by ball."
                    : competition === "test"
                      ? "Tests remembered for how they finished, ready to replay ball by ball."
                      : `The latest ${c.label} finals, ready to replay ball by ball.`}
            </p>
          </div>
          <Link
            href={competitionPath(competition, "/matches")}
            className="text-sm text-primary underline-offset-4 hover:underline"
          >
            All matches
          </Link>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {featured.slice(0, 6).map((m) => (
            <li key={m.match_id} className="flex">
              <MatchCard competition={competition} match={m.summary} headline={m.headline} />
            </li>
          ))}
        </ul>
      </section>

      <SeasonSnapshotSection competition={competition} />

      <BiggestSwings competition={competition} />

      <section aria-labelledby="capabilities-heading" className="flex flex-col gap-6">
        <div>
          <h2 id="capabilities-heading" className="text-xl font-semibold tracking-tight">
            What you can do
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Each capability shipped as a complete, tested slice, from data to model to interface.
          </p>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {capabilities(c).map(({ icon: Icon, title, body, path }) => (
            <li key={title} className="flex">
              <Link
                href={competitionPath(competition, path)}
                className="group flex w-full flex-col gap-3 rounded-2xl border border-border bg-card/70 p-5 transition-colors hover:border-primary/40"
              >
                <span className="flex items-center justify-between">
                  <span className="grid size-9 place-items-center rounded-lg bg-accent text-primary">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <ArrowRight
                    className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
                    aria-hidden="true"
                  />
                </span>
                <span className="font-medium">{title}</span>
                <span className="text-sm leading-relaxed text-muted-foreground">{body}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
