"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { useCompetition } from "@/components/competition/use-competition";
import { competitionPath, getCompetition } from "@/lib/competitions";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: ReactNode;
  /** Within the competition being browsed ("/players" is /ipl/players); none for the current page. */
  href?: string;
}

/**
 * Where a page sits: the competition, then each level down to the page itself (last, unlinked).
 * Every detail page uses it, so the trail looks and reads the same everywhere.
 */
export function Breadcrumbs({ items, className }: { items: Crumb[]; className?: string }) {
  const competition = useCompetition();
  const trail: Crumb[] = [{ label: getCompetition(competition).label, href: "" }, ...items];
  return (
    <nav aria-label="Breadcrumb" className={cn("text-sm text-muted-foreground", className)}>
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
        {trail.map((crumb, i) => {
          const last = i === trail.length - 1;
          return (
            <li key={i} className="flex min-w-0 items-center gap-1.5">
              {crumb.href !== undefined && !last ? (
                <Link
                  href={competitionPath(competition, crumb.href)}
                  className="truncate rounded-sm transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className="truncate text-foreground">
                  {crumb.label}
                </span>
              )}
              {!last && (
                <ChevronRight className="size-3.5 shrink-0 opacity-60" aria-hidden="true" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
