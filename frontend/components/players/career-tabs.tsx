import Link from "next/link";

import type { CareerLine, PlayerCareers } from "@/lib/api/types";
import {
  COMPETITIONS,
  competitionPath,
  getCompetition,
  isCompetitionId,
  type CompetitionId,
} from "@/lib/competitions";
import { scrollRegion } from "@/lib/a11y";
import { rate } from "@/lib/players";
import { cn } from "@/lib/utils";

const ALL_T20 = "t20";

function competitionLabel(id: string): string {
  return isCompetitionId(id) ? getCompetition(id).label : id === ALL_T20 ? "All T20" : id;
}

/** The player's page in every competition they played in, as tabs. */
export function CareerTabs({
  careers,
  current,
}: {
  careers: PlayerCareers;
  current: CompetitionId;
}) {
  const played = new Set(careers.careers.map((c) => c.competition));
  const tabs = COMPETITIONS.filter((c) => played.has(c.id));
  if (tabs.length < 2 && !played.has(ALL_T20)) return null;
  return (
    <nav aria-label="Competitions" className="flex flex-wrap gap-1.5">
      {tabs.map((c) => (
        <Link
          key={c.id}
          href={competitionPath(c.id, `/players/${careers.player_id}`)}
          aria-current={c.id === current ? "page" : undefined}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            c.id === current
              ? "border-primary/50 bg-primary/10 text-primary"
              : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground",
          )}
        >
          {c.label}
        </Link>
      ))}
      {played.has(ALL_T20) && (
        <a
          href="#careers"
          className="rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          All T20
        </a>
      )}
    </nav>
  );
}

function versusPar(value: number | null, par: number | null, higherIsBetter: boolean): string {
  if (value === null || par === null) return "";
  const delta = value - par;
  const better = higherIsBetter ? delta > 0 : delta < 0;
  return `${delta > 0 ? "+" : delta < 0 ? "−" : "±"}${Math.abs(delta).toFixed(1)} ${better ? "above" : "below"} par`;
}

function Row({ line, total }: { line: CareerLine; total: boolean }) {
  const span =
    line.first_season === line.last_season
      ? line.first_season
      : `${line.first_season}–${line.last_season}`;
  return (
    <tr className={cn(total && "bg-muted/40 font-medium")}>
      <th scope="row" className="px-3 py-2 text-left font-medium">
        {competitionLabel(line.competition)}
        <span className="block text-xs font-normal text-muted-foreground">{span}</span>
      </th>
      <td className="px-3 py-2 text-right font-mono tabular-nums">{line.matches}</td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">{line.runs}</td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">
        {line.strike_rate !== null ? rate(line.strike_rate, 1) : "–"}
        <span className="block text-xs font-normal text-muted-foreground">
          {versusPar(line.strike_rate, line.par_strike_rate, true)}
        </span>
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">{line.wickets}</td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">
        {line.economy !== null ? rate(line.economy) : "–"}
        <span className="block text-xs font-normal text-muted-foreground">
          {versusPar(line.economy, line.par_economy, false)}
        </span>
      </td>
    </tr>
  );
}

/** One line per competition played, then all T20 cricket together, each against its own par. */
export function CareerTable({ careers }: { careers: PlayerCareers }) {
  if (careers.careers.length < 2) return null;
  const th = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
  return (
    <section id="careers" aria-labelledby="careers-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="careers-heading" className="text-lg font-semibold tracking-tight">
          Every T20 competition
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          The player&apos;s record in each competition, each measured against that
          competition&apos;s own par, and all T20 cricket together.
        </p>
      </div>
      <div className="overflow-x-auto" {...scrollRegion("Career in every T20 competition")}>
        <table className="w-full min-w-[36rem] text-sm">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                Competition
              </th>
              <th scope="col" className={th}>
                Matches
              </th>
              <th scope="col" className={th}>
                Runs
              </th>
              <th scope="col" className={th}>
                Strike rate
              </th>
              <th scope="col" className={th}>
                Wickets
              </th>
              <th scope="col" className={th}>
                Economy
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {careers.careers.map((line) => (
              <Row key={line.competition} line={line} total={line.competition === ALL_T20} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
