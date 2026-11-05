import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DayView } from "@/components/on-this-day/day-view";
import { getDay } from "@/lib/api/on-this-day";
import { dateSlug, dayLabel, parseDateSlug } from "@/lib/on-this-day";

export async function generateMetadata({
  params,
}: PageProps<"/on-this-day/[date]">): Promise<Metadata> {
  const date = parseDateSlug((await params).date);
  if (!date) return {};
  const label = dayLabel(date);
  const card = `/on-this-day/${dateSlug(date)}/card`;
  return {
    title: `On this day: ${label}`,
    description: `Cricket matches played on ${label} in past years across the IPL, BBL, PSL, CPL, SA20, T20Is, ODIs and Tests, with each one's standout performance and biggest swing.`,
    openGraph: { images: [{ url: card, width: 1200, height: 630 }] },
    twitter: { images: [card] },
  };
}

export default async function OnThisDatePage({
  params,
  searchParams,
}: PageProps<"/on-this-day/[date]">) {
  const date = parseDateSlug((await params).date);
  if (!date) notFound();
  const [result, raw] = await Promise.all([getDay(date), searchParams]);
  return <DayView date={date} result={result} raw={raw} today={false} />;
}
