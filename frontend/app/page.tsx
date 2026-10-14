import { ArrowDown, BookOpen, Info } from "lucide-react";
import Link from "next/link";

import { CompetitionPicker, type PickerCard } from "@/components/competition/competition-picker";
import { Scene3D } from "@/components/three/scene-3d";
import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "@/components/ui/section-header";
import { COMPETITIONS, competitionPath, seasonLabel, type Competition } from "@/lib/competitions";
import { featuredMatches, seasonSnapshot } from "@/lib/featured";

function pickerCard(c: Competition): PickerCard {
  const latest = seasonSnapshot(c.id);
  return {
    id: c.id,
    href: competitionPath(c.id),
    label: c.label,
    name: c.name,
    format: c.format,
    span: `${seasonLabel(c.id, c.firstSeason)} to ${latest.label}`,
    champion: latest.champion,
    featured: featuredMatches(c.id)[0]?.headline ?? null,
  };
}

const FIRST_SEASON = Math.min(...COMPETITIONS.map((c) => c.firstSeason));
const FORMATS = new Set(COMPETITIONS.map((c) => c.format)).size;

export default function HomePage() {
  const groups = [
    { title: "Leagues", cards: COMPETITIONS.filter((c) => c.teamType === "club").map(pickerCard) },
    {
      title: "Internationals",
      cards: COMPETITIONS.filter((c) => c.teamType === "national").map(pickerCard),
    },
  ];
  return (
    <div className="flex flex-col gap-14">
      <section className="glass relative grid grid-cols-1 items-center gap-6 overflow-hidden rounded-3xl px-6 pt-12 pb-6 sm:px-10 sm:pt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:gap-4 lg:py-10 lg:pr-4">
        <div className="lg:py-6">
          <Badge
            variant="outline"
            className="mb-6 font-mono text-[11px] tracking-wide text-primary"
          >
            T20, one-day and Test cricket · ball by ball
          </Badge>
          <h1 className="max-w-3xl text-display font-semibold text-balance">
            Decode the game.
            <span className="block text-muted-foreground">Predict the next move.</span>
          </h1>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-pretty text-muted-foreground sm:text-lg">
            Every delivery of the IPL, men&apos;s T20 internationals, ODIs and Tests, and the BBL,
            PSL, CPL and SA20, as interactive analytics: replay any match with each side&apos;s
            chance of winning after every ball, measure any career against par, and read any
            batter-vs-bowler rivalry without over-reading small samples.
          </p>
          <dl className="mt-8 grid max-w-md grid-cols-3 gap-4 border-t border-border pt-5">
            {[
              [String(COMPETITIONS.length), "competitions"],
              [String(FORMATS), "formats"],
              [String(FIRST_SEASON), "the first season"],
            ].map(([value, label]) => (
              <div key={label} className="flex flex-col-reverse gap-0.5">
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="font-mono text-2xl font-semibold tracking-tight tabular-nums">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          <a
            href="#choose"
            className="mt-8 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85"
          >
            Choose a competition
            <ArrowDown className="size-4" aria-hidden="true" />
          </a>
        </div>
        <Scene3D
          scene="stadium"
          poster={{
            dark: "/3d/posters/stadium-night.webp",
            light: "/3d/posters/stadium-day.webp",
          }}
          width={1200}
          height={900}
          label="A cricket stadium under floodlights at night, or in sunshine by day, circling slowly"
          minWidth={1024}
          className="mx-auto w-full max-w-xl lg:max-w-none"
        />
      </section>

      <section
        id="choose"
        aria-labelledby="choose-heading"
        className="flex scroll-mt-20 flex-col gap-6"
      >
        <SectionHeader
          id="choose-heading"
          title="Choose a competition"
          description="Each has its own matches, players, teams and models. Switch any time from the top bar."
        />
        <CompetitionPicker groups={groups} />
      </section>

      <section aria-labelledby="more-heading" className="flex flex-col gap-4">
        <SectionHeader id="more-heading" title="How it works" />
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <li>
            <Link
              href="/about"
              className="group flex h-full items-start gap-3 rounded-2xl border border-border bg-card p-5 shadow-elev-1 transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-elev-2"
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
              className="group flex h-full items-start gap-3 rounded-2xl border border-border bg-card p-5 shadow-elev-1 transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-elev-2"
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
