"use client";

import { Legend, sidesOf } from "@/components/replay/chart-parts";
import { ManhattanChart } from "@/components/replay/manhattan-chart";
import type { Timeline } from "@/lib/api/types";

/** Over by over: the runs in each over of both innings as the Manhattan chart. */
export function OversPanel({ timeline, cursor }: { timeline: Timeline; cursor: number }) {
  const sides = sidesOf(timeline);
  return (
    <section aria-labelledby="overs-heading" className="panel">
      <div className="flex flex-col gap-0.5">
        <h2 id="overs-heading" className="text-sm font-semibold">
          Over by over
        </h2>
        <p className="text-xs text-muted-foreground">Runs in each over, with the wickets on top.</p>
      </div>
      <div className="mt-4 h-72" data-testid="overs-chart">
        <ManhattanChart timeline={timeline} cursor={cursor} />
      </div>
      <div className="mt-3">
        <Legend sides={sides} />
      </div>
    </section>
  );
}
