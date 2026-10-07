"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

import { useCompetition } from "@/components/competition/use-competition";
import { competitionPath } from "@/lib/competitions";

/**
 * A link to a page of the competition being browsed: `href="/players/x"` goes to
 * `/t20i/players/x` on a T20I page. Server components render it like `Link`, so
 * they need not know which competition they are in.
 */
export function CompetitionLink({
  href,
  ...props
}: Omit<ComponentProps<typeof Link>, "href"> & { href: string }) {
  const competition = useCompetition();
  return <Link href={competitionPath(competition, href)} {...props} />;
}
