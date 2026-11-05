import type { Metadata } from "next";
import { connection } from "next/server";

import { DayView } from "@/components/on-this-day/day-view";
import { VisitorDate } from "@/components/on-this-day/visitor-date";
import { getDay } from "@/lib/api/on-this-day";
import { dateSlug, HOME_TIME_ZONE, todayIn } from "@/lib/on-this-day";

export async function generateMetadata(): Promise<Metadata> {
  await connection();
  const slug = dateSlug(todayIn(HOME_TIME_ZONE));
  return {
    title: "On this day in cricket",
    description:
      "The matches played on today's date in past years across the IPL, BBL, PSL, CPL, SA20, T20Is, ODIs and Tests, with each one's standout performance and biggest swing.",
    // Today's page shows one date's page: that page is the one to index.
    alternates: { canonical: `/on-this-day/${slug}` },
    openGraph: { images: [{ url: `/on-this-day/${slug}/card`, width: 1200, height: 630 }] },
  };
}

export default async function OnThisDayPage({ searchParams }: PageProps<"/on-this-day">) {
  // Today's date, so rendered per request (the API's answers are cached).
  await connection();
  const date = todayIn(HOME_TIME_ZONE);
  const [result, raw] = await Promise.all([getDay(date), searchParams]);
  return (
    <>
      <VisitorDate shown={date} />
      <DayView date={date} result={result} raw={raw} today />
    </>
  );
}
