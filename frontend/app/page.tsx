import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CircleCheck,
  CircleDashed,
  Loader,
  Swords,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ROADMAP, type MilestoneStatus } from "@/lib/roadmap";
import { cn } from "@/lib/utils";

const CAPABILITIES: { icon: LucideIcon; title: string; body: string; milestone: string }[] = [
  {
    icon: Activity,
    title: "Ball-by-ball replay",
    body: "Relive any IPL match delivery by delivery, with the scoreboard, momentum and probability moving as it happened.",
    milestone: "M2",
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
            href="/about"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85"
          >
            How CricIQ works
            <ArrowRight className="size-4" />
          </Link>
        </div>
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
