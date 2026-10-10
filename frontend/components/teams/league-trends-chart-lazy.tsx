"use client";

import dynamic from "next/dynamic";

/** The league trends chart, loaded after the page: its charting library stays out of the
 * JavaScript the page needs to paint. The placeholder keeps its height. */
export const LeagueTrendsChartLazy = dynamic(
  () => import("@/components/teams/league-trends-chart").then((m) => m.LeagueTrendsChart),
  { ssr: false, loading: () => <div className="h-72 animate-pulse rounded-xl bg-muted/40" /> },
);
