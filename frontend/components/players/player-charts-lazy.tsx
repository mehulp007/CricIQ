"use client";

import dynamic from "next/dynamic";

import { afterLoad } from "@/lib/animation";

// The player charts load once the page has loaded and gone idle: the charting library stays out of
// the JavaScript the page needs first. Each placeholder keeps its chart's size.
const charts = () => afterLoad().then(() => import("@/components/players/player-charts"));
export const SeasonCharts = dynamic(() => charts().then((m) => m.SeasonCharts), {
  ssr: false,
  loading: () => (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="h-64 animate-pulse rounded-xl bg-muted/40" />
      <div className="h-64 animate-pulse rounded-xl bg-muted/40" />
    </div>
  ),
});
export const FormChart = dynamic(() => charts().then((m) => m.FormChart), {
  ssr: false,
  loading: () => <div className="h-60 animate-pulse rounded-xl bg-muted/40" />,
});
