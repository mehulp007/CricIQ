import Link from "next/link";

import type { CareerLine, CareerRatings, PlayerCareers } from "@/lib/api/types";
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

const cell = "px-3 py-2 text-right font-mono tabular-nums";

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
      <td className={cell}>{line.matches}</td>
      <td className={cell}>{line.runs}</td>
      <td className={cell}>{line.batting_average !== null ? rate(line.batting_average) : "–"}</td>
      <td className={cell}>
        {line.strike_rate !== null ? rate(line.strike_rate, 1) : "–"}
        <span className="block text-xs font-normal text-muted-foreground">
          {versusPar(line.strike_rate, line.par_strike_rate, true)}
        </span>
      </td>
      <td className={cell}>
        {line.hundreds}/{line.fifties}
      </td>
      <td className={cell}>
        {line.high ?? "–"}
        {line.high !== null && line.high_not_out ? "*" : ""}
      </td>
      <td className={cell}>{line.wickets}</td>
      <td className={cell}>{line.bowling_average !== null ? rate(line.bowling_average) : "–"}</td>
      <td className={cell}>
        {line.economy !== null ? rate(line.economy) : "–"}
        <span className="block text-xs font-normal text-muted-foreground">
          {versusPar(line.economy, line.par_economy, false)}
        </span>
      </td>
      <td className={cell}>
        {line.best_wickets !== null && line.best_runs !== null
          ? `${line.best_wickets}/${line.best_runs}`
          : "–"}
      </td>
    </tr>
  );
}

/** One line per competition played, with all T20 cricket together after the T20 lines, each
 * against its own par. */
export function CareerTable({ careers }: { careers: PlayerCareers }) {
  if (careers.careers.length < 2) return null;
  const th = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
  return (
    <section id="careers" aria-labelledby="careers-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="careers-heading" className="text-lg font-semibold tracking-tight">
          Every competition
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          The player&apos;s record in each competition, each measured against that
          competition&apos;s own par, and all their T20 cricket together. A Test strike rate and a
          T20 one are different things, so compare each with its par.
        </p>
      </div>
      <div className="overflow-x-auto" {...scrollRegion("Career in every competition")}>
        <table className="w-full min-w-[56rem] text-sm">
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
                Average
              </th>
              <th scope="col" className={th}>
                Strike rate
              </th>
              <th scope="col" className={th}>
                <abbr title="Hundreds / fifties">100s/50s</abbr>
              </th>
              <th scope="col" className={th}>
                <abbr title="Highest score">Best</abbr>
              </th>
              <th scope="col" className={th}>
                Wickets
              </th>
              <th scope="col" className={th}>
                <abbr title="Bowling average">Average</abbr>
              </th>
              <th scope="col" className={th}>
                Economy
              </th>
              <th scope="col" className={th}>
                <abbr title="Best bowling in an innings">Best</abbr>
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

function RatingCell({ value }: { value: number | null | undefined }) {
  return (
    <td className={cell}>
      {value === null || value === undefined ? (
        <span className="text-muted-foreground">–</span>
      ) : (
        value
      )}
    </td>
  );
}

const RATED = {
  batting: ["scoring", "survival", "impact"],
  bowling: ["economy", "wickets", "impact"],
} as const;

/** Headline CricIQ Ratings in each competition, each a percentile among that competition's
 * own players, so the formats sit side by side but are never mixed into one number. */
export function CareerRatingsTable({ ratings }: { ratings: CareerRatings }) {
  if (ratings.lines.length < 2) return null;
  const th = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
  const label = (role: "batting" | "bowling", key: string) =>
    ratings.lines.flatMap((l) => l[role]).find((r) => r.key === key)?.label ?? key;
  const value = (line: (typeof ratings.lines)[number], role: "batting" | "bowling", key: string) =>
    line[role].find((r) => r.key === key)?.rating;
  return (
    <section aria-labelledby="career-ratings-heading" className="flex flex-col gap-3">
      <div>
        <h2 id="career-ratings-heading" className="text-lg font-semibold tracking-tight">
          Ratings in every competition
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          The same skills side by side, each a percentile (0-100) among that competition&apos;s
          qualified players over all its seasons. A dash means too few balls to rate.
        </p>
      </div>
      <div className="overflow-x-auto" {...scrollRegion("Ratings in every competition")}>
        <table className="w-full min-w-[40rem] text-sm">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" rowSpan={2} className={cn(th, "text-left align-bottom")}>
                Competition
              </th>
              <th scope="colgroup" colSpan={3} className={cn(th, "text-center")}>
                Batting
              </th>
              <th scope="colgroup" colSpan={3} className={cn(th, "text-center")}>
                Bowling
              </th>
            </tr>
            <tr>
              {(["batting", "bowling"] as const).flatMap((role) =>
                RATED[role].map((key) => (
                  <th key={`${role}-${key}`} scope="col" className={th}>
                    {label(role, key)}
                  </th>
                )),
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {ratings.lines.map((line) => (
              <tr key={line.competition}>
                <th scope="row" className="px-3 py-2 text-left font-medium">
                  {competitionLabel(line.competition)}
                </th>
                {(["batting", "bowling"] as const).flatMap((role) =>
                  RATED[role].map((key) => (
                    <RatingCell key={`${role}-${key}`} value={value(line, role, key)} />
                  )),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
