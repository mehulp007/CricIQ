import { StatTile } from "@/components/ui/stat-tile";
import { getMeta } from "@/lib/api/client";
import { type CompetitionId } from "@/lib/competitions";
import { seasonSnapshot } from "@/lib/featured";
import { formatDate } from "@/lib/format";
import { seasonSpan } from "@/lib/freshness";

/**
 * A competition's headline numbers: how much of it the data holds and the latest season's
 * scoring. Left out while the API is unavailable (the rest of the page still works).
 */
export async function HeadlineNumbers({ competition }: { competition: CompetitionId }) {
  let meta;
  try {
    meta = await getMeta(competition);
  } catch {
    return null;
  }
  const matches = meta.seasons.reduce((sum, s) => sum + s.matches, 0);
  if (matches === 0) return null;
  const latest = seasonSnapshot(competition);
  return (
    <section aria-label="In numbers" className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <StatTile
        label="Matches"
        value={matches.toLocaleString("en-IN")}
        hint="Every one ball by ball"
      />
      <StatTile label="Seasons" value={meta.seasons.length} hint={seasonSpan(meta) ?? undefined} />
      <StatTile
        label={`${latest.label} first innings`}
        value={latest.first_innings_average.toFixed(0)}
        hint="The average total batting first"
      />
      <StatTile
        label="Latest match"
        value={
          meta.latest_match_date ? (
            <span className="text-xl sm:text-2xl">{formatDate(meta.latest_match_date)}</span>
          ) : (
            "—"
          )
        }
        hint="Updated from Cricsheet"
      />
    </section>
  );
}
