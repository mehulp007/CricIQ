import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { getCompetition, isCompetitionId } from "@/lib/competitions";

/** Series and tournaments are kept for international cricket only. Checked here, before
 * the pages' loading state starts streaming, so other competitions get a real 404. */
export default async function SeriesLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ competition: string }>;
}) {
  const { competition } = await params;
  if (!isCompetitionId(competition) || getCompetition(competition).teamType !== "national") {
    notFound();
  }
  return children;
}
