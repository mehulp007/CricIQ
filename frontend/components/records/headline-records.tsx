import Link from "next/link";

import { RecordCard } from "@/components/records/record-card";
import { SectionHeader } from "@/components/ui/section-header";
import { getRecords } from "@/lib/api/client";
import { competitionPath, type CompetitionId } from "@/lib/competitions";

// The four on a competition's home: the best innings, spell, team total and stand.
const HEADLINES = [
  "highest-scores",
  "best-bowling-figures",
  "highest-totals",
  "highest-partnerships",
];

/** A strip of headline records on the competition home. Left out while the API sleeps. */
export async function HeadlineRecords({ competition }: { competition: CompetitionId }) {
  let records;
  try {
    records = (await getRecords(competition)).records;
  } catch {
    return null;
  }
  const picked = HEADLINES.map((key) => records.find((r) => r.record.key === key)).filter(
    (r) => r !== undefined,
  );
  if (picked.length === 0) return null;
  return (
    <section aria-labelledby="records-heading" className="flex flex-col gap-6">
      <SectionHeader
        id="records-heading"
        title="Headline records"
        description="The highest score, best bowling, highest total and biggest stand in the ball-by-ball data."
        action={
          <Link
            href={competitionPath(competition, "/records")}
            className="text-primary underline-offset-4 hover:underline"
          >
            All records
          </Link>
        }
      />
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {picked.map((leader) => (
          <li key={leader.record.key} className="flex min-w-0">
            <RecordCard leader={leader} />
          </li>
        ))}
      </ul>
    </section>
  );
}
