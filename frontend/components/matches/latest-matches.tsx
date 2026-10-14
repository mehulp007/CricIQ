import Link from "next/link";

import { MatchCard } from "@/components/match/match-card";
import { SectionHeader } from "@/components/ui/section-header";
import { getMatches } from "@/lib/api/client";
import { competitionPath, getCompetition, type CompetitionId } from "@/lib/competitions";

const COUNT = 3;

/**
 * The newest matches in the live data, so each sync's additions are one click
 * away. Left out while the API sleeps (the bundled replays below still work).
 */
export async function LatestMatches({ competition }: { competition: CompetitionId }) {
  let matches;
  try {
    matches = (await getMatches(competition, { sort: "latest", pageSize: COUNT })).items;
  } catch {
    return null;
  }
  if (matches.length === 0) return null;
  return (
    <section aria-labelledby="latest-heading" className="flex flex-col gap-6">
      <SectionHeader
        id="latest-heading"
        title="Latest matches"
        description={`The newest ${getCompetition(competition).noun.replace(/ match$/, "")} matches in the data, updated from Cricsheet after each match.`}
        action={
          <Link
            href={competitionPath(competition, "/matches")}
            className="text-primary underline-offset-4 hover:underline"
          >
            All matches
          </Link>
        }
      />
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {matches.map((match) => (
          <li key={match.match_id} className="flex">
            <MatchCard competition={competition} match={match} />
          </li>
        ))}
      </ul>
    </section>
  );
}
