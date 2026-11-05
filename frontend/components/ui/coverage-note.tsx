import { Database } from "lucide-react";

import { cn } from "@/lib/utils";

export interface CoverageInfo {
  first_season_label: string | null;
  last_season_label: string | null;
  matches: number;
}

/** "IPL 2008–2026, 1,243 matches" (or just the matches when no season is known). */
export function coverageText(competition: string, coverage: CoverageInfo): string {
  const matches = `${coverage.matches.toLocaleString("en-US")} ${coverage.matches === 1 ? "match" : "matches"}`;
  const { first_season_label: first, last_season_label: last } = coverage;
  if (!first || !last) return `${competition}: ${matches}`;
  const span = first === last ? first : `${first}–${last}`;
  return `${competition} ${span}, ${matches}`;
}

/** Says which matches a page's figures come from: the ball-by-ball data, nothing older. */
export function CoverageNote({
  competition,
  coverage,
  className,
}: {
  competition: string;
  coverage: CoverageInfo;
  className?: string;
}) {
  return (
    <p className={cn("flex items-center gap-2 text-xs text-muted-foreground", className)}>
      <Database className="size-3.5 shrink-0" aria-hidden="true" />
      <span>
        In CricIQ&apos;s ball-by-ball data: {coverageText(competition, coverage)}.
      </span>
    </p>
  );
}
