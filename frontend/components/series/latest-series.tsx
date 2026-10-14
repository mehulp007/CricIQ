import Link from "next/link";

import { SeriesCard } from "@/components/series/series-card";
import { SectionHeader } from "@/components/ui/section-header";
import { getSeriesList } from "@/lib/api/client";
import { competitionPath, getCompetition, type CompetitionId } from "@/lib/competitions";

const COUNT = 3;

/**
 * The newest series and tournaments in the live data, with their scores so far.
 * International competitions only; left out while the API is unavailable.
 */
export async function LatestSeries({ competition }: { competition: CompetitionId }) {
  if (getCompetition(competition).teamType !== "national") return null;
  let items;
  try {
    items = (await getSeriesList(competition, { pageSize: COUNT })).items;
  } catch {
    return null;
  }
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="latest-series-heading" className="flex flex-col gap-6">
      <SectionHeader
        id="latest-series-heading"
        title="Latest series"
        description="The newest series and tournaments in the data, with the score so far where more matches may follow."
        action={
          <Link
            href={competitionPath(competition, "/series")}
            className="text-primary underline-offset-4 hover:underline"
          >
            All series
          </Link>
        }
      />
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((s) => (
          <li key={s.event_id} className="flex">
            <SeriesCard competition={competition} series={s} />
          </li>
        ))}
      </ul>
    </section>
  );
}
