import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  GitCompareArrows,
  Play,
  Swords,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { MatchCard } from "@/components/match/match-card";
import { LatestMatches } from "@/components/matches/latest-matches";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { FEATURED, SNAPSHOT } from "@/lib/featured";
import { WIN_PROBABILITY } from "@/lib/models";
import { signed } from "@/lib/players";

const CAPABILITIES: { icon: LucideIcon; title: string; body: string; href: string }[] = [
  {
    icon: Activity,
    title: "Ball-by-ball replay",
    body: "Relive any IPL match delivery by delivery: live scoreboard, scorecard, commentary, worm and Manhattan charts.",
    href: "/matches",
  },
  {
    icon: BrainCircuit,
    title: "Explainable win probability",
    body: "Each side's chance after every ball with the reasons in cricket terms, and the projected first-innings total with an 80% range that holds up.",
    href: "/matches/1181768",
  },
  {
    icon: Users,
    title: "Player Lab",
    body: "Every player's career measured against par, with CricIQ Ratings that allow for sample size, splits, win probability added and similar players.",
    href: "/players",
  },
  {
    icon: GitCompareArrows,
    title: "Compare players",
    body: "Any two players over the same seasons: numbers against par, ratings with intervals, and their seasons lined up by year or by age.",
    href: "/compare",
  },
  {
    icon: Swords,
    title: "Matchup Lab",
    body: "Any batter against any bowler, read three ways so a few dozen balls of history are never over-read, plus next-ball odds.",
    href: "/matchups",
  },
  {
    icon: BrainCircuit,
    title: "Model Insights",
    body: "How each model was built and tested: calibration, season-by-season backtests, rejected features and limitations.",
    href: "/models",
  },
];

const LEADERS: { key: keyof typeof SNAPSHOT.leaders; label: string; unit: string }[] = [
  { key: "runs", label: "Most runs", unit: "runs" },
  { key: "wickets", label: "Most wickets", unit: "wickets" },
  { key: "runs_above_par", label: "Most runs above par", unit: "runs" },
  { key: "runs_saved", label: "Most runs saved vs par", unit: "runs" },
];

function SeasonSnapshot() {
  const s = SNAPSHOT;
  const change =
    s.previous_first_innings_average !== null
      ? s.first_innings_average - s.previous_first_innings_average
      : null;
  return (
    <section aria-labelledby="season-heading" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="season-heading" className="text-xl font-semibold tracking-tight">
            IPL {s.season} at a glance
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {s.matches} matches
            {s.champion && <> · champions {s.champion}</>}. Par adjusts for the season and phase, so
            the last two cards reward quality, not just volume.
          </p>
        </div>
        <Link
          href={`/matches?season=${s.season}`}
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          All {s.season} matches
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
              {change !== null && (
                <>
                  {signed(change)} on {s.season - 1} ·{" "}
                </>
              )}
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
                    href={`/players/${leader.player_id}?from=${s.season}&to=${s.season}`}
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

function BiggestSwings() {
  const swings = WIN_PROBABILITY.swings.slice(0, 3);
  return (
    <section aria-labelledby="swings-heading" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="swings-heading" className="text-xl font-semibold tracking-tight">
            The biggest swings in IPL history
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Single balls that moved the win probability the most. Open one to replay the moment.
          </p>
        </div>
        <Link
          href="/models#swings-heading"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Top 10
        </Link>
      </div>
      <ul className="grid gap-4 md:grid-cols-3">
        {swings.map((s) => (
          <li key={`${s.match_id}-${s.seq_no}`} className="flex">
            <Link
              href={`/matches/${s.match_id}?ball=${s.innings_no}.${s.seq_no}`}
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
                {s.teams}, {s.season} {s.stage !== "League" ? s.stage.toLowerCase() : ""} · ball{" "}
                {s.ball_label} · {s.result}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function OverviewPage() {
  return (
    <div className="flex flex-col gap-14">
      <section className="glass relative overflow-hidden rounded-3xl px-6 py-12 sm:px-10 sm:py-16">
        <Badge variant="outline" className="mb-6 font-mono text-[11px] tracking-wide text-primary">
          IPL · 2008 onward
        </Badge>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
          Decode the game.
          <span className="block text-muted-foreground">Predict the next move.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          CricIQ turns every IPL delivery since 2008 into interactive analytics. Replay any match
          with each side&apos;s chance of winning after every ball, explore and compare any
          player&apos;s career against par, and read any batter-vs-bowler rivalry without
          over-reading small samples. Every number comes from a tested model you can inspect.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/matches/1181768"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85"
          >
            <Play className="size-4" aria-hidden="true" />
            Replay the 2019 final
          </Link>
          <Link
            href="/players"
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            <Users className="size-4" aria-hidden="true" />
            Explore players
          </Link>
          <Link
            href="/matchups"
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            <Swords className="size-4" aria-hidden="true" />
            Compare a batter and a bowler
          </Link>
        </div>
      </section>

      <Suspense fallback={null}>
        <LatestMatches />
      </Suspense>

      <section aria-labelledby="featured-heading" className="flex flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="featured-heading" className="text-xl font-semibold tracking-tight">
              Featured replays
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Iconic IPL matches, ready to replay ball by ball.
            </p>
          </div>
          <Link href="/matches" className="text-sm text-primary underline-offset-4 hover:underline">
            All matches
          </Link>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {FEATURED.slice(0, 6).map((m) => (
            <li key={m.match_id} className="flex">
              <MatchCard match={m.summary} headline={m.headline} />
            </li>
          ))}
        </ul>
      </section>

      <SeasonSnapshot />

      <BiggestSwings />

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
          {CAPABILITIES.map(({ icon: Icon, title, body, href }) => (
            <li key={title} className="flex">
              <Link
                href={href}
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
