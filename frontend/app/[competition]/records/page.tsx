import type { Metadata } from "next";
import { connection } from "next/server";

import { RecordCard } from "@/components/records/record-card";
import { CoverageNote } from "@/components/ui/coverage-note";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SectionHeader } from "@/components/ui/section-header";
import { getRecords } from "@/lib/api/client";
import { getCompetition, isCompetitionId, type CompetitionId } from "@/lib/competitions";
import { BALL_BY_BALL_NOTE, GROUP_LABELS } from "@/lib/records";

export async function generateMetadata({
  params,
}: PageProps<"/[competition]/records">): Promise<Metadata> {
  const { competition } = await params;
  if (!isCompetitionId(competition)) return {};
  const c = getCompetition(competition);
  return {
    title: `${c.label} records`,
    description: `Career, innings, partnership, team and season records in ${c.collective}, from every ball in CricIQ's data, plus the fastest fifties, biggest overs and biggest swings.`,
  };
}

export default async function RecordsPage({ params }: PageProps<"/[competition]/records">) {
  // Rendered per request, like the other API pages (a build needs no API); the API's
  // answer is still cached for a day.
  await connection();
  const competition = (await params).competition as CompetitionId;
  const c = getCompetition(competition);
  const hub = await getRecords(competition);

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-3">
        <PageHeader
          eyebrow={c.label}
          title="Records"
          description={`Career, innings, partnership, team and season records in ${c.collective}. Every figure is counted from the ball-by-ball data, so a record set before the data begins is not here.`}
        />
        <CoverageNote competition={c.label} coverage={hub.coverage} />
      </div>
      {hub.records.length === 0 ? (
        <EmptyState
          title="No records yet"
          description="This competition has no matches in the data."
        />
      ) : (
        hub.groups.map((group) => {
          const items = hub.records.filter((r) => r.record.group === group);
          return (
            <section key={group} aria-labelledby={`group-${group}`} className="flex flex-col gap-4">
              <SectionHeader
                id={`group-${group}`}
                title={GROUP_LABELS[group]}
                description={group === "ball_by_ball" ? BALL_BY_BALL_NOTE : undefined}
              />
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {items.map((leader) => (
                  <li key={leader.record.key} className="flex min-w-0">
                    <RecordCard leader={leader} />
                  </li>
                ))}
              </ul>
            </section>
          );
        })
      )}
    </div>
  );
}
