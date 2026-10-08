import { Info, Trophy } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CompetitionLink } from "@/components/competition/competition-link";
import { MatchCard } from "@/components/match/match-card";
import { TeamSwatch } from "@/components/match/team-badge";
import { Panel } from "@/components/players/profile-parts";
import { StandingsTable } from "@/components/series/standings-table";
import { ApiError, getSeries } from "@/lib/api/client";
import type { SeriesDetail, SeriesMatch, SeriesSummary } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { getCompetition, isCompetitionId, isTest, type CompetitionId } from "@/lib/competitions";
import { rate } from "@/lib/players";
import { dateRange, kindLabel, seriesNotes, seriesTitle } from "@/lib/series";
import { cn } from "@/lib/utils";

async function load(competition: CompetitionId, id: string): Promise<SeriesDetail> {
  if (!/^[a-z0-9-]{1,120}$/.test(id)) notFound();
  try {
    return await getSeries(competition, id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/series/[id]">): Promise<Metadata> {
  const { competition, id } = await params;
  if (!isCompetitionId(competition) || getCompetition(competition).teamType !== "national") {
    return {};
  }
  try {
    const { summary } = await load(competition, id);
    return {
      title: seriesTitle(summary),
      description: `${seriesTitle(summary)}: ${summary.result_text}. Every match, ${summary.kind === "tournament" ? "the tables and knockouts, " : ""}the top run-scorers and wicket-takers, and the players who moved the results most.`,
    };
  } catch {
    return { title: "Series" };
  }
}

function Scoreline({ summary }: { summary: SeriesSummary }) {
  const [a, b] = summary.teams;
  if (!a || !b) return null;
  const side = (team: typeof a, align: "left" | "right") => (
    <div className={cn("flex min-w-0 flex-col gap-1", align === "right" && "items-end text-right")}>
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <TeamSwatch color={team.color} />
        <CompetitionLink
          href={`/teams/${team.franchise_id}`}
          className="truncate underline-offset-4 hover:text-foreground hover:underline"
        >
          {team.name}
        </CompetitionLink>
      </span>
      <span className="font-mono text-5xl font-semibold tracking-tight tabular-nums">
        {team.wins}
      </span>
      <span className="text-xs text-muted-foreground">{team.wins === 1 ? "win" : "wins"}</span>
    </div>
  );
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-4">
      {side(a, "left")}
      <span className="pb-6 text-sm text-muted-foreground">v</span>
      {side(b, "right")}
    </div>
  );
}

function Champion({ summary }: { summary: SeriesSummary }) {
  if (!summary.champion) return null;
  return (
    <div className="flex items-center gap-4">
      <Trophy className="size-8 shrink-0 text-team-b" aria-hidden="true" />
      <div className="flex flex-col gap-0.5">
        <span className="text-xs tracking-wide text-muted-foreground uppercase">Champions</span>
        <span className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <TeamSwatch color={summary.champion.color} />
          {summary.champion.name}
        </span>
        {summary.runner_up && (
          <span className="text-sm text-muted-foreground">
            Runners-up: {summary.runner_up.name}
          </span>
        )}
      </div>
    </div>
  );
}

/** The round (unless the card sits under it), and how far the winner came back. */
function headline(entry: SeriesMatch, withRound: boolean): string | undefined {
  const parts: string[] = [];
  if (withRound && entry.round) parts.push(entry.round);
  const m = entry.summary;
  if (entry.winner_low !== null && entry.winner_low !== undefined && entry.winner_low < 0.25) {
    const winner = m.winner_id === m.team_a.team_season_id ? m.team_a.name : m.team_b.name;
    parts.push(`${winner} won from a ${Math.round(100 * entry.winner_low)}% chance`);
  }
  return parts.length ? parts.join(" · ") : undefined;
}

function Matches({
  competition,
  entries,
  withRound = true,
}: {
  competition: CompetitionId;
  entries: SeriesMatch[];
  withRound?: boolean;
}) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {entries.map((e) => (
        <li key={e.summary.match_id} className="flex">
          <MatchCard
            competition={competition}
            match={e.summary}
            headline={headline(e, withRound)}
          />
        </li>
      ))}
    </ul>
  );
}

function Performers({ detail, test }: { detail: SeriesDetail; test: boolean }) {
  const th = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
  const cell = "px-3 py-2 text-right font-mono tabular-nums";
  const name = (id: string, label: string, team: string) => (
    <th scope="row" className="px-3 py-2 text-left font-normal">
      <CompetitionLink
        href={`/players/${id}`}
        className="underline-offset-4 hover:text-primary hover:underline"
      >
        {label}
      </CompetitionLink>
      <span className="ml-2 font-mono text-xs text-muted-foreground">{team}</span>
    </th>
  );
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Panel id="batters-heading" title="Most runs">
        <div className="overflow-x-auto" {...scrollRegion("Runs in this event")}>
          <table className="w-full min-w-[30rem] text-sm">
            <thead className="border-b border-border">
              <tr>
                <th scope="col" className={cn(th, "text-left")}>
                  Batter
                </th>
                <th scope="col" className={th}>
                  Runs
                </th>
                <th scope="col" className={th}>
                  Average
                </th>
                <th scope="col" className={th}>
                  {test ? "100s / 50s" : "Strike rate"}
                </th>
                <th scope="col" className={th}>
                  Best
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {detail.batters.map((b) => (
                <tr key={b.player_id}>
                  {name(b.player_id, b.name, b.team)}
                  <td className={cn(cell, "text-foreground")}>{b.runs}</td>
                  <td className={cell}>{b.outs ? rate(b.runs / b.outs) : "—"}</td>
                  <td className={cell}>
                    {test
                      ? `${b.hundreds} / ${b.fifties}`
                      : b.balls
                        ? rate((100 * b.runs) / b.balls, 1)
                        : "—"}
                  </td>
                  <td className={cell}>
                    {b.high}
                    {b.high_not_out ? "*" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel id="bowlers-heading" title="Most wickets">
        <div className="overflow-x-auto" {...scrollRegion("Wickets in this event")}>
          <table className="w-full min-w-[30rem] text-sm">
            <thead className="border-b border-border">
              <tr>
                <th scope="col" className={cn(th, "text-left")}>
                  Bowler
                </th>
                <th scope="col" className={th}>
                  Wickets
                </th>
                <th scope="col" className={th}>
                  Average
                </th>
                <th scope="col" className={th}>
                  Economy
                </th>
                <th scope="col" className={th}>
                  Best
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {detail.bowlers.map((b) => (
                <tr key={b.player_id}>
                  {name(b.player_id, b.name, b.team)}
                  <td className={cn(cell, "text-foreground")}>{b.wickets}</td>
                  <td className={cell}>{b.wickets ? rate(b.runs / b.wickets) : "—"}</td>
                  <td className={cell}>{b.balls ? rate((6 * b.runs) / b.balls) : "—"}</td>
                  <td className={cell}>
                    {b.best_wickets}/{b.best_runs}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function Decisive({ detail, test }: { detail: SeriesDetail; test: boolean }) {
  if (detail.decisive.length === 0) return null;
  return (
    <Panel
      id="decisive-heading"
      title="Who moved the results most"
      lede={
        test
          ? "Expected result added over the series: how much each player's balls moved their side's expected result (a win counts one, a draw a half), from the win probability model."
          : "Win probability added over the event: how much each player's balls moved their side's chance of winning, in matches won, from the win probability model."
      }
    >
      <ol className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {detail.decisive.map((d, i) => (
          <li key={d.player_id} className="flex items-center gap-3 rounded-xl bg-muted/40 p-3">
            <span className="w-5 font-mono text-xs text-muted-foreground tabular-nums">
              {i + 1}
            </span>
            <span className="flex min-w-0 flex-col">
              <CompetitionLink
                href={`/players/${d.player_id}`}
                className="truncate font-medium underline-offset-4 hover:text-primary hover:underline"
              >
                {d.name}
              </CompetitionLink>
              <span className="text-xs text-muted-foreground">
                {d.team} · {d.matches} {d.matches === 1 ? "match" : "matches"}
              </span>
            </span>
            <span className="ml-auto font-mono text-sm tabular-nums">
              {d.added >= 0 ? "+" : "−"}
              {Math.abs(d.added).toFixed(2)}
            </span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

export default async function SeriesPage({ params }: PageProps<"/[competition]/series/[id]">) {
  const { competition: raw, id } = await params;
  if (!isCompetitionId(raw) || getCompetition(raw).teamType !== "national") notFound();
  const competition = raw as CompetitionId;
  const detail = await load(competition, id);
  const { summary } = detail;
  const test = isTest(competition);
  const notes = seriesNotes(summary);
  const pair = summary.kind === "series" && summary.teams.length === 2 ? summary.teams : null;

  return (
    <div className="flex flex-col gap-8">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <CompetitionLink href="/series" className="hover:text-foreground">
          Series
        </CompetitionLink>
        <span aria-hidden="true"> / </span>
        <span className="text-foreground">{seriesTitle(summary)}</span>
      </nav>

      <header className="flex flex-col gap-2">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          {kindLabel(summary, getCompetition(competition).format)} ·{" "}
          {dateRange(summary.start_date, summary.end_date)}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">{seriesTitle(summary)}</h1>
        <p className="text-lg text-muted-foreground">{summary.result_text}</p>
      </header>

      <section
        aria-label="Result"
        className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5 sm:p-6"
      >
        {summary.champion ? <Champion summary={summary} /> : <Scoreline summary={summary} />}
        {notes.length > 0 && (
          <ul className="flex flex-col gap-1.5 border-t border-border pt-4 text-sm text-muted-foreground">
            {notes.map((n) => (
              <li key={n} className="flex gap-2">
                <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                {n}
              </li>
            ))}
          </ul>
        )}
        {pair && (
          <CompetitionLink
            href={`/teams/h2h?a=${pair[0].franchise_id}&b=${pair[1].franchise_id}`}
            className="text-sm text-primary underline-offset-4 hover:underline"
          >
            {pair[0].name} v {pair[1].name}: every meeting
          </CompetitionLink>
        )}
      </section>

      {detail.rounds.length > 0 ? (
        detail.rounds.map((round, i) => {
          const entries = detail.matches.filter((m) =>
            round.matches.some((r) => r.match_id === m.summary.match_id),
          );
          const headingId = `round-${i}`;
          return (
            <section key={round.name} aria-labelledby={headingId} className="flex flex-col gap-4">
              <h2 id={headingId} className="text-xl font-semibold tracking-tight">
                {round.name}
              </h2>
              {round.standings.length > 0 && (
                <StandingsTable rows={round.standings} label={`${round.name} table`} />
              )}
              {round.knockout ? (
                <Matches competition={competition} entries={entries} withRound={false} />
              ) : (
                <details className="group rounded-xl border border-border">
                  <summary className="cursor-pointer px-4 py-3 text-sm text-muted-foreground hover:text-foreground">
                    {entries.length} {entries.length === 1 ? "match" : "matches"}
                  </summary>
                  <div className="p-4 pt-0">
                    <Matches competition={competition} entries={entries} withRound={false} />
                  </div>
                </details>
              )}
            </section>
          );
        })
      ) : (
        <section aria-labelledby="matches-heading" className="flex flex-col gap-4">
          <h2 id="matches-heading" className="text-xl font-semibold tracking-tight">
            {summary.matches === 1 ? "The match" : "The matches"}
          </h2>
          <Matches competition={competition} entries={detail.matches} />
        </section>
      )}

      {detail.rounds.some((r) => r.standings.length > 0) && (
        <p className="flex gap-2 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          Tables count the matches in the data: two points for a win, one for a tie or no result,
          then net run rate. Matches abandoned before a ball, and Afghanistan&apos;s matches
          (Cricsheet has none), are not in it, so a table can differ from the official one.
        </p>
      )}

      {(detail.batters.length > 0 || detail.bowlers.length > 0) && (
        <Performers detail={detail} test={test} />
      )}
      <Decisive detail={detail} test={test} />
    </div>
  );
}
