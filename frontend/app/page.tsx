import { ArrowRight, BookOpen, Info } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import {
  COMPETITIONS,
  UPCOMING,
  competitionPath,
  seasonLabel,
  type Competition,
} from "@/lib/competitions";
import { featuredMatches, seasonSnapshot } from "@/lib/featured";

function CompetitionCard({ c }: { c: Competition }) {
  const latest = seasonSnapshot(c.id);
  const lead = featuredMatches(c.id)[0];
  return (
    <Link
      href={competitionPath(c.id)}
      className="group flex h-full flex-col gap-3 rounded-2xl border border-border bg-card/70 p-5 transition-colors hover:border-primary/40 hover:bg-card"
    >
      <span className="flex items-center justify-between gap-2">
        <span className="font-mono text-xl font-semibold tracking-tight">{c.label}</span>
        <ArrowRight
          className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
          aria-hidden="true"
        />
      </span>
      <span className="font-medium group-hover:text-primary">{c.name}</span>
      <span className="text-sm text-muted-foreground">
        {seasonLabel(c.id, c.firstSeason)} to {latest.label}
        {latest.champion && ` · ${latest.champion} the latest champions`}
      </span>
      {lead && (
        <span className="mt-auto text-xs text-muted-foreground">Featured: {lead.headline}</span>
      )}
    </Link>
  );
}

export default function HomePage() {
  const leagues = COMPETITIONS.filter((c) => c.teamType === "club");
  const internationals = COMPETITIONS.filter((c) => c.teamType === "national");
  return (
    <div className="flex flex-col gap-14">
      <section className="glass relative overflow-hidden rounded-3xl px-6 py-12 sm:px-10 sm:py-16">
        <Badge variant="outline" className="mb-6 font-mono text-[11px] tracking-wide text-primary">
          T20 and one-day cricket · ball by ball
        </Badge>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
          Decode the game.
          <span className="block text-muted-foreground">Predict the next move.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          CricIQ turns every delivery of the IPL, men&apos;s T20 internationals and ODIs, and the
          BBL, PSL, CPL and SA20 into interactive analytics: replay any match with each side&apos;s
          chance of winning after every ball, explore any player&apos;s career against par in every
          competition, and read any batter-vs-bowler rivalry without over-reading small samples.
          Every number comes from a tested model you can inspect.
        </p>
      </section>

      <section aria-labelledby="choose-heading" className="flex flex-col gap-6">
        <div>
          <h2 id="choose-heading" className="text-xl font-semibold tracking-tight">
            Choose a competition
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Each has its own matches, players, teams and models. Switch any time from the top bar.
          </p>
        </div>
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-medium text-muted-foreground">Leagues</h3>
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {leagues.map((c) => (
              <li key={c.id}>
                <CompetitionCard c={c} />
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-medium text-muted-foreground">Internationals</h3>
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {internationals.map((c) => (
              <li key={c.id}>
                <CompetitionCard c={c} />
              </li>
            ))}
            {UPCOMING.map((f) => (
              <li key={f.label}>
                <div
                  aria-disabled="true"
                  className="flex h-full flex-col gap-3 rounded-2xl border border-dashed border-border p-5 text-muted-foreground"
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xl font-semibold tracking-tight">
                      {f.label}
                    </span>
                    <Badge variant="outline" className="text-[10px] font-normal">
                      Coming in {f.milestone}
                    </Badge>
                  </span>
                  <span className="font-medium">{f.name}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="more-heading" className="flex flex-col gap-4">
        <h2 id="more-heading" className="text-xl font-semibold tracking-tight">
          How it works
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2">
          <li>
            <Link
              href="/about"
              className="group flex h-full items-start gap-3 rounded-2xl border border-border bg-card/70 p-5 transition-colors hover:border-primary/40"
            >
              <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              <span className="flex flex-col gap-1">
                <span className="font-medium group-hover:text-primary">
                  About &amp; Methodology
                </span>
                <span className="text-sm text-muted-foreground">
                  Every number on the site, explained in plain terms.
                </span>
              </span>
            </Link>
          </li>
          <li>
            <Link
              href="/writeup"
              className="group flex h-full items-start gap-3 rounded-2xl border border-border bg-card/70 p-5 transition-colors hover:border-primary/40"
            >
              <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              <span className="flex flex-col gap-1">
                <span className="font-medium group-hover:text-primary">The write-up</span>
                <span className="text-sm text-muted-foreground">
                  How the models were built and tested, and what did not work.
                </span>
              </span>
            </Link>
          </li>
        </ul>
      </section>
    </div>
  );
}
