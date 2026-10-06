import { RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { getMeta } from "@/lib/api/client";
import { seasonRange } from "@/lib/featured";
import { freshnessLabel, seasonSpan } from "@/lib/freshness";

/** The competition and its seasons, from the bundled replays (shown while data loads). */
export function SeasonBadge({ span = seasonRange() }: { span?: string }) {
  return (
    <Badge variant="outline" className="font-mono text-[11px] text-muted-foreground">
      IPL · {span}
    </Badge>
  );
}

/**
 * The seasons the live data holds and how fresh it is ("Data updated 2 Apr 2027 ·
 * 3 new matches"). Falls back to the bundled season range while the API sleeps.
 */
export async function DataBadges() {
  let meta;
  try {
    meta = await getMeta();
  } catch {
    return <SeasonBadge />;
  }
  const freshness = freshnessLabel(meta);
  return (
    <>
      {freshness ? (
        <Badge
          variant="outline"
          className="hidden gap-1.5 text-[11px] text-muted-foreground sm:inline-flex"
          data-testid="data-freshness"
        >
          <RefreshCw className="size-3" aria-hidden="true" />
          {freshness}
        </Badge>
      ) : null}
      <SeasonBadge span={seasonSpan(meta) ?? undefined} />
    </>
  );
}
