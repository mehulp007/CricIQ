import type { Metadata } from "next";

import { Pagination } from "@/components/matches/pagination";
import { PlayerFilters } from "@/components/players/player-filters";
import { PlayerTable } from "@/components/players/player-table";
import { getMeta, getPlayers, type PlayerRoleFilter, type PlayerSort } from "@/lib/api/client";
import {
  competitionPath,
  getCompetition,
  isCompetitionId,
  type CompetitionId,
} from "@/lib/competitions";
import { PLAYER_SORTS, ROLE_FILTERS, parseSeason } from "@/lib/players";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/players">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.label} Player Lab`,
    description: `Every ${c.label} player since ${c.firstSeason}: batting and bowling profiles measured against par for the same seasons and phases.`,
  };
}

const PAGE_SIZE = 30;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function oneOf<T extends string>(value: string | undefined, allowed: readonly { value: T }[]) {
  return allowed.find((a) => a.value === value)?.value;
}

export default async function PlayersPage({
  params: route,
  searchParams,
}: PageProps<"/[competition]/players">) {
  const competition = (await route).competition as CompetitionId;
  const c = getCompetition(competition);
  const raw = await searchParams;
  const q = first(raw.q)?.trim().slice(0, 64) || undefined;
  const role: PlayerRoleFilter | undefined = oneOf(first(raw.role), ROLE_FILTERS);
  const sort: PlayerSort | undefined = oneOf(first(raw.sort), PLAYER_SORTS);
  const season = parseSeason(raw.season);
  const team = first(raw.team)?.toUpperCase();
  const page = Math.max(1, Number(first(raw.page)) || 1);

  const [meta, result] = await Promise.all([
    getMeta(competition),
    getPlayers(competition, { q, role, season, team, sort, page, pageSize: PAGE_SIZE }),
  ]);

  const params: Record<string, string> = {};
  if (q) params.q = q;
  if (role) params.role = role;
  if (season) params.season = String(season);
  if (team) params.team = team;
  if (sort) params.sort = sort;
  const scoped = season || team;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Player Lab</h1>
        <p className="max-w-3xl text-muted-foreground">
          Every {c.label} player since {c.firstSeason}. Profiles measure batting and bowling against
          par (the {c.label}&apos;s own): what an average player would have done in the same seasons
          and phases.
        </p>
      </header>

      <PlayerFilters
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
        {result.total === 1 ? "player" : "players"}
        {scoped && " · numbers for the selected season and team"}
      </p>

      {result.items.length > 0 ? (
        <PlayerTable players={result.items} />
      ) : (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-muted-foreground">
          No players match{q ? ` “${q}”` : " these filters"}.
        </p>
      )}

      <Pagination
        page={page}
        pageSize={PAGE_SIZE}
        total={result.total}
        params={params}
        basePath={competitionPath(competition, "/players")}
        labels={{ previous: "Previous", next: "Next" }}
      />
    </div>
  );
}
