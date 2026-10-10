"use client";

import dynamic from "next/dynamic";

/** The seasons chart, loaded after the page: its charting library stays out of the JavaScript the
 * page needs to paint. The placeholder keeps its height. */
export const SeasonsChartLazy = dynamic(
  () => import("@/components/teams/seasons-chart").then((m) => m.SeasonsChart),
  { ssr: false, loading: () => <div className="h-64 animate-pulse rounded-xl bg-muted/40" /> },
);
