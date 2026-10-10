"use client";

import dynamic from "next/dynamic";

// The player charts load after the page paints: the charting library stays out of the JavaScript
// the page needs first. Each placeholder keeps its chart's size.
export const SeasonCharts = dynamic(
  () => import("@/components/players/player-charts").then((m) => m.SeasonCharts),
  {
    ssr: false,
    loading: () => (
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="h-64 animate-pulse rounded-xl bg-muted/40" />
        <div className="h-64 animate-pulse rounded-xl bg-muted/40" />
      </div>
    ),
  },
);
export const FormChart = dynamic(
  () => import("@/components/players/player-charts").then((m) => m.FormChart),
  { ssr: false, loading: () => <div className="h-60 animate-pulse rounded-xl bg-muted/40" /> },
);
