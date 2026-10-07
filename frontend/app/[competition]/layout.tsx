import { notFound } from "next/navigation";

import { RememberCompetition } from "@/components/competition/remember-competition";
import { COMPETITIONS, isCompetitionId } from "@/lib/competitions";

// Only the competitions the site serves have pages; any other segment is a 404.
export const dynamicParams = false;

export function generateStaticParams() {
  return COMPETITIONS.map((c) => ({ competition: c.id }));
}

export default async function CompetitionLayout({
  children,
  params,
}: LayoutProps<"/[competition]">) {
  const { competition } = await params;
  if (!isCompetitionId(competition)) notFound();
  return (
    <>
      <RememberCompetition id={competition} />
      {children}
    </>
  );
}
