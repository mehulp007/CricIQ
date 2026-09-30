import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CircleCheck,
  CircleDashed,
  Loader,
  Play,
  Swords,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { MatchCard } from "@/components/match/match-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FEATURED } from "@/lib/featured";
import { ROADMAP, type MilestoneStatus } from "@/lib/roadmap";
import { cn } from "@/lib/utils";

const CAPABILITIES: { icon: LucideIcon; title: string; body: string; milestone: string }[] = [
  {
    icon: Activity,
    title: "Ball-by-ball replay",
    body: "Relive any IPL match delivery by delivery, with a live scoreboard, scorecard, commentary and worm and Manhattan charts.",
    milestone: "Live",
  },
  {
    icon: BrainCircuit,
    title: "Explainable win probability",
    body: "Calibrated models that say who is ahead, by how much, and why, in the language of cricket.",
    milestone: "M3",
  },
  {
    icon: Users,
    title: "Player intelligence",
    body: "Contextual profiles by phase, venue, situation and opposition, not just averages and strike rates.",
    milestone: "M5",
  },
  {
    icon: Swords,
    title: "Matchup lab",
    body: "Batter vs bowler analysis that respects sample size instead of over-reading 12 balls of history.",
    milestone: "M6",
  },
];

const STATUS_ICON: Record<MilestoneStatus, LucideIcon> = {
  done: CircleCheck,
  active: Loader,
  planned: CircleDashed,
};

const STATUS_LABEL: Record<MilestoneStatus, string> = {
  done: "Done",
  active: "In progress",
  planned: "Planned",
};

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
          CricIQ turns every IPL delivery into interactive analytics: historical match replays,
          calibrated win probability, probabilistic score projection, and player and matchup
          intelligence. Every number comes from a tested model you can inspect.
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
            href="/matches"
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            Explore all matches
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </section>

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

      <section aria-labelledby="capabilities-heading" className="flex flex-col gap-6">
        <div>
          <h2 id="capabilities-heading" className="text-xl font-semibold tracking-tight">
            What you&apos;ll be able to do
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Each capability ships as a complete, tested slice, from data to model to interface.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {CAPABILITIES.map(({ icon: Icon, title, body, milestone }) => (
            <Card key={title} className="bg-card/70">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span className="grid size-9 place-items-center rounded-lg bg-accent text-primary">
                    <Icon className="size-4" />
                  </span>
                  <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">
                    {milestone}
                  </Badge>
                </div>
                <CardTitle className="mt-3">{title}</CardTitle>
                <CardDescription className="leading-relaxed">{body}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section aria-labelledby="roadmap-heading" className="flex flex-col gap-6">
        <div>
          <h2 id="roadmap-heading" className="text-xl font-semibold tracking-tight">
            Build progress
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Built in vertical slices. Nothing is shown until it is real.
          </p>
        </div>
        <Card className="bg-card/70">
          <CardContent>
            <ol className="flex flex-col divide-y divide-border">
              {ROADMAP.map((m) => {
                const Icon = STATUS_ICON[m.status];
                return (
                  <li key={m.id} className="flex items-start gap-4 py-4 first:pt-0 last:pb-0">
                    <Icon
                      aria-hidden="true"
                      className={cn(
                        "mt-0.5 size-5 shrink-0",
                        m.status === "done" && "text-positive",
                        m.status === "active" && "text-team-b",
                        m.status === "planned" && "text-muted-foreground",
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        <span className="mr-2 font-mono text-xs text-muted-foreground">{m.id}</span>
                        {m.title}
                      </p>
                      <p className="mt-0.5 text-sm text-muted-foreground">{m.summary}</p>
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {STATUS_LABEL[m.status]}
                    </span>
                  </li>
                );
              })}
            </ol>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
