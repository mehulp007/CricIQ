import type { Metadata } from "next";

import { StudioBuilder } from "@/components/studio/studio-builder";
import { CoverageNote } from "@/components/ui/coverage-note";
import { PageHeader } from "@/components/ui/page-header";
import { getMatch, getMatches, getStudioOptions, runStudio } from "@/lib/api/client";
import {
  getCompetition,
  isCompetitionId,
  seasonLabel,
  type CompetitionId,
} from "@/lib/competitions";
import { formatDate } from "@/lib/format";
import { parseState } from "@/lib/studio";
import { toSearchParams } from "@/lib/url";

const RECENT_MATCHES = 40;

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/studio">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.label} chart studio`,
    description: `Build a chart from ${c.label} ball-by-ball data without code: pick players, measures and a template, then download it as PNG, SVG or CSV.`,
  };
}

export default async function StudioPage({
  params,
  searchParams,
}: PageProps<"/[competition]/studio">) {
  const competition = (await params).competition as CompetitionId;
  const c = getCompetition(competition);
  const [options, recent] = await Promise.all([
    getStudioOptions(competition),
    getMatches(competition, { pageSize: RECENT_MATCHES }).catch(() => null),
  ]);
  let initial = parseState(toSearchParams(await searchParams), options);
  if (initial.template === "match" && initial.match === null && recent?.items[0]) {
    initial = { ...initial, match: recent.items[0].match_id };
  }
  const [result, match] = await Promise.all([
    initial.template === "match" ? null : runStudio(competition, initial.spec).catch(() => null),
    initial.match === null ? null : getMatch(competition, initial.match).catch(() => null),
  ]);

  const matches = (recent?.items ?? []).map((m) => ({
    value: String(m.match_id),
    label: `${m.team_a.name} v ${m.team_b.name} · ${formatDate(m.date)}`,
  }));
  if (match && !matches.some((m) => m.value === String(match.summary.match_id))) {
    matches.unshift({
      value: String(match.summary.match_id),
      label: `${match.summary.team_a.name} v ${match.summary.team_b.name} · ${formatDate(match.summary.date)}`,
    });
  }
  const span =
    options.coverage.first_season && options.coverage.last_season
      ? `${seasonLabel(competition, options.coverage.first_season)}–${seasonLabel(competition, options.coverage.last_season)}`
      : "";

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Make a chart"
        title="Chart Studio"
        description={`Build a chart from ${c.label} ball-by-ball data without writing code: start from a template or pick the data, measures and style yourself, then download it as PNG, SVG or CSV. Every figure comes with the query that computed it.`}
      />
      <CoverageNote competition={c.label} coverage={options.coverage} />
      <StudioBuilder
        // A new link (a saved design, the back button) starts the builder afresh.
        key={JSON.stringify(initial)}
        competition={competition}
        competitionLabel={c.label}
        teamWord={c.teamType === "national" ? "Side" : "Team"}
        options={options}
        initial={initial}
        initialResult={result}
        initialMatch={match}
        matches={matches}
        footerSpan={span}
      />
    </div>
  );
}
