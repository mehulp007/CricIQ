import type { Metadata } from "next";

import { MatchCard } from "@/components/match/match-card";
import { MatchFilters } from "@/components/matches/match-filters";
import { Pagination } from "@/components/matches/pagination";
import { getMatches, getMeta } from "@/lib/api/client";
import {
  competitionPath,
  getCompetition,
  isCompetitionId,
  type CompetitionId,
} from "@/lib/competitions";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/matches">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.label} Match Explorer`,
    description: `Browse every ${c.noun} since ${c.firstSeason} and replay any of them ball by ball.`,
  };
}

const PAGE_SIZE = 24;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function MatchesPage({
  params: route,
  searchParams,
}: PageProps<"/[competition]/matches">) {
  const competition = (await route).competition as CompetitionId;
  const c = getCompetition(competition);
  const raw = await searchParams;
  const season = Number(first(raw.season)) || undefined;
  const team = first(raw.team)?.toUpperCase();
  const playoffs = first(raw.playoffs) === "true" ? true : undefined;
  const page = Math.max(1, Number(first(raw.page)) || 1);

  const [meta, result] = await Promise.all([
    getMeta(competition),
    getMatches(competition, { season, team, playoffs, page, pageSize: PAGE_SIZE }),
  ]);

  const params: Record<string, string> = {};
  if (season) params.season = String(season);
  if (team) params.team = team;
  if (playoffs) params.playoffs = "true";

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Match Explorer</h1>
        <p className="text-muted-foreground">
          Every {c.noun} since {c.firstSeason}. Open any match to replay it ball by ball.
        </p>
      </header>

      <MatchFilters
        options={{
          seasons: meta.seasons.map((s) => ({ year: s.year, label: s.label })).reverse(),
          teams: meta.franchises.map((f) => ({
            id: f.franchise_id,
            name: f.name,
            active: f.is_active,
          })),
        }}
      />

      <p className="text-sm text-muted-foreground" aria-live="polite">
        <span className="font-mono text-foreground tabular-nums">{result.total}</span>{" "}
        {result.total === 1 ? "match" : "matches"}
      </p>

      {result.items.length > 0 ? (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {result.items.map((match) => (
            <li key={match.match_id} className="flex">
              <MatchCard competition={competition} match={match} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-muted-foreground">
          No matches for these filters.
        </p>
      )}

      <Pagination
        page={page}
        pageSize={PAGE_SIZE}
        total={result.total}
        params={params}
        basePath={competitionPath(competition, "/matches")}
      />
    </div>
  );
}
