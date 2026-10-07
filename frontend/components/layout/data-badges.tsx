import { RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { getMeta } from "@/lib/api/client";
import type { Meta } from "@/lib/api/types";
import { COMPETITIONS } from "@/lib/competitions";
import { combinedFreshness, freshnessLabel } from "@/lib/freshness";

/**
 * How fresh the data is across every competition ("Data updated 2 Apr 2027 · 3 new
 * matches"): a sync updates them together. Shows nothing while the API sleeps.
 */
export async function DataFreshness() {
  const found = await Promise.allSettled(COMPETITIONS.map((c) => getMeta(c.id)));
  const metas = found
    .filter((r): r is PromiseFulfilledResult<Meta> => r.status === "fulfilled")
    .map((r) => r.value);
  if (metas.length === 0) return null;
  const freshness = freshnessLabel(combinedFreshness(metas));
  if (!freshness) return null;
  return (
    <Badge
      variant="outline"
      className="hidden gap-1.5 text-[11px] text-muted-foreground sm:inline-flex"
      data-testid="data-freshness"
    >
      <RefreshCw className="size-3" aria-hidden="true" />
      {freshness}
    </Badge>
  );
}
