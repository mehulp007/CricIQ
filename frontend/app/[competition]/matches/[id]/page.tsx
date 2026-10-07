import { CalendarDays, MapPin, Trophy } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { TeamBadge } from "@/components/match/team-badge";
import { MatchCenter } from "@/components/replay/match-center";
import { ApiError, getTimeline } from "@/lib/api/client";
import type { Timeline } from "@/lib/api/types";
import {
  competitionPath,
  isCompetitionId,
  seasonLabel,
  type CompetitionId,
} from "@/lib/competitions";
import { featuredMatches, isFeatured, loadFeaturedTimeline } from "@/lib/featured";
import { formatDate, stageLabel } from "@/lib/format";
import { modelsFor } from "@/lib/models";

// Featured replays are prerendered from bundled data; any other match renders
// on first request and is then cached.
export function generateStaticParams({ params }: { params: { competition: string } }) {
  if (!isCompetitionId(params.competition)) return [];
  return featuredMatches(params.competition).map((m) => ({ id: String(m.match_id) }));
}

async function loadTimeline(competition: CompetitionId, id: string): Promise<Timeline> {
  const matchId = Number(id);
  if (!Number.isInteger(matchId) || matchId <= 0) notFound();
  if (isFeatured(competition, matchId)) {
    return (await loadFeaturedTimeline(competition, matchId))!;
  }
  try {
    return await getTimeline(competition, matchId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/matches/[id]">): Promise<Metadata> {
  const { competition, id } = await params;
  try {
    const { summary } = await loadTimeline(competition as CompetitionId, id);
    return {
      title: `${summary.team_a.franchise_id} vs ${summary.team_b.franchise_id}, ${seasonLabel(competition as CompetitionId, summary.season)} replay`,
      description: `${summary.team_a.name} vs ${summary.team_b.name}, ${formatDate(summary.date)}. ${summary.result_text}. Replay it ball by ball.`,
    };
  } catch {
    return { title: "Match replay" };
  }
}

export default async function MatchPage({ params }: PageProps<"/[competition]/matches/[id]">) {
  const { id } = await params;
  const competition = (await params).competition as CompetitionId;
  const timeline = await loadTimeline(competition, id);
  const { summary } = timeline;

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <Link href={competitionPath(competition, "/matches")} className="hover:text-foreground">
          Matches
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="text-foreground">
          {seasonLabel(competition, summary.season)} ·{" "}
          {stageLabel(summary.stage, summary.match_number)}
        </span>
      </nav>

      <header className="flex flex-col gap-3">
        <h1 className="flex flex-wrap items-center gap-x-3 gap-y-1 text-2xl font-semibold tracking-tight sm:text-3xl">
          <span>{summary.team_a.name}</span>
          <span className="text-base font-normal text-muted-foreground">vs</span>
          <span>{summary.team_b.name}</span>
        </h1>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-3">
            <TeamBadge shortName={summary.team_a.franchise_id} color={summary.team_a.color} />
            <TeamBadge shortName={summary.team_b.franchise_id} color={summary.team_b.color} />
          </span>
          <span className="flex items-center gap-1.5">
            <CalendarDays className="size-4" aria-hidden="true" />
            {formatDate(summary.date)}
          </span>
          <span className="flex items-center gap-1.5">
            <MapPin className="size-4" aria-hidden="true" />
            {summary.venue.name}, {summary.venue.city}
          </span>
          {summary.player_of_match.length > 0 && (
            <span className="flex items-center gap-1.5">
              <Trophy className="size-4" aria-hidden="true" />
              {summary.player_of_match.join(", ")}
            </span>
          )}
        </div>
      </header>

      <MatchCenter
        timeline={timeline}
        competition={competition}
        simulator={modelsFor(competition).simulator !== null}
      />
    </div>
  );
}
