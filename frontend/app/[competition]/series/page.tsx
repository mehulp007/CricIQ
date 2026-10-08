import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { TeamSwatch } from "@/components/match/team-badge";
import { Pagination } from "@/components/matches/pagination";
import { SeriesCard } from "@/components/series/series-card";
import { SeriesFilters } from "@/components/series/series-filters";
import { CompetitionLink } from "@/components/competition/competition-link";
import { getMeta, getSeriesList } from "@/lib/api/client";
import {
  competitionPath,
  getCompetition,
  isCompetitionId,
  type CompetitionId,
} from "@/lib/competitions";
import { groupTournaments } from "@/lib/series";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/series">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.label} series and tournaments`,
    description: `Every ${c.noun} series and tournament since ${c.firstSeason}: results, tables, knockouts and top performers, with the World Cup and other major tournaments by edition.`,
  };
}

const PAGE_SIZE = 24;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function SeriesListPage({
  params: route,
  searchParams,
}: PageProps<"/[competition]/series">) {
  const { competition: raw } = await route;
  if (!isCompetitionId(raw) || getCompetition(raw).teamType !== "national") notFound();
  const competition = raw as CompetitionId;
  const c = getCompetition(competition);
  const query = await searchParams;
  const year = Number(first(query.year)) || undefined;
  const team = first(query.team)?.toUpperCase();
  const kindParam = first(query.kind);
  const kind = kindParam === "series" || kindParam === "tournament" ? kindParam : undefined;
  const page = Math.max(1, Number(first(query.page)) || 1);
  const filtered = Boolean(year || team || kind);

  const [meta, result, majors] = await Promise.all([
    getMeta(competition),
    getSeriesList(competition, { year, team, kind, page, pageSize: PAGE_SIZE }),
    filtered ? null : getSeriesList(competition, { major: true, pageSize: 100 }),
  ]);
  const tournaments = majors ? groupTournaments(majors.items) : [];

  const params: Record<string, string> = {};
  if (year) params.year = String(year);
  if (team) params.team = team;
  if (kind) params.kind = kind;

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Series and tournaments</h1>
        <p className="max-w-3xl text-muted-foreground">
          Every {c.noun} series and tournament since {c.firstSeason}, from Cricsheet&apos;s record
          of each match&apos;s event. A series is between two sides; a tournament between more, with
          its tables and knockouts.
        </p>
      </header>

      {tournaments.length > 0 && (
        <section aria-labelledby="majors-heading" className="flex flex-col gap-4">
          <h2 id="majors-heading" className="text-xl font-semibold tracking-tight">
            Major tournaments
          </h2>
          <ul className="grid gap-4 md:grid-cols-2">
            {tournaments.map((t) => (
              <li
                key={t.id}
                className="flex flex-col gap-3 rounded-2xl border border-border bg-card/70 p-5"
              >
                <h3 className="font-semibold tracking-tight">{t.name}</h3>
                <ol className="flex flex-col divide-y divide-border text-sm">
                  {t.editions.map((e) => (
                    <li key={e.event_id} className="flex items-center gap-3 py-1.5">
                      <CompetitionLink
                        href={`/series/${e.event_id}`}
                        className="w-14 font-mono text-xs text-primary tabular-nums underline-offset-4 hover:underline"
                      >
                        {e.season}
                      </CompetitionLink>
                      {e.champion ? (
                        <span className="flex min-w-0 items-center gap-2">
                          <TeamSwatch color={e.champion.color} />
                          <span className="truncate">{e.champion.name}</span>
                          {e.runner_up && (
                            <span className="truncate text-xs text-muted-foreground">
                              beat {e.runner_up.name}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">{e.result_text}</span>
                      )}
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="all-heading" className="flex flex-col gap-5">
        <h2 id="all-heading" className="text-xl font-semibold tracking-tight">
          {filtered ? "Matching series and tournaments" : "All series and tournaments"}
        </h2>
        <SeriesFilters
          options={{
            years: result.years,
            teams: meta.franchises
              .map((f) => ({ id: f.franchise_id, name: f.name }))
              .sort((a, b) => a.name.localeCompare(b.name)),
          }}
        />
        <p className="text-sm text-muted-foreground" aria-live="polite">
          <span className="font-mono text-foreground tabular-nums">{result.total}</span>{" "}
          {result.total === 1 ? "series or tournament" : "series and tournaments"}
        </p>
        {result.items.length > 0 ? (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {result.items.map((s) => (
              <li key={s.event_id} className="flex">
                <SeriesCard competition={competition} series={s} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-xl border border-dashed border-border p-10 text-center text-muted-foreground">
            No series or tournaments for these filters.
          </p>
        )}
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={result.total}
          params={params}
          basePath={competitionPath(competition, "/series")}
        />
      </section>
    </div>
  );
}
