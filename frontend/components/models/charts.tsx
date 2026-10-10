"use client";

import dynamic from "next/dynamic";

import { SERIES } from "@/lib/models";

export type { BallBacktestRow } from "@/components/models/charts-recharts";

// The charts load after the page paints: the charting library stays out of the JavaScript a page
// needs first. Each placeholder keeps its chart's height.
function Placeholder({ height }: { height: string }) {
  return <div className={`${height} animate-pulse rounded-xl bg-muted/40`} />;
}

export const ReliabilityChart = dynamic(
  () => import("@/components/models/charts-recharts").then((m) => m.ReliabilityChart),
  { ssr: false, loading: () => <Placeholder height="h-72" /> },
);
export const BacktestChart = dynamic(
  () => import("@/components/models/charts-recharts").then((m) => m.BacktestChart),
  { ssr: false, loading: () => <Placeholder height="h-64" /> },
);
export const LevelCalibrationChart = dynamic(
  () => import("@/components/models/charts-recharts").then((m) => m.LevelCalibrationChart),
  { ssr: false, loading: () => <Placeholder height="h-72" /> },
);
export const ProjectionBacktestChart = dynamic(
  () => import("@/components/models/charts-recharts").then((m) => m.ProjectionBacktestChart),
  { ssr: false, loading: () => <Placeholder height="h-64" /> },
);
export const BallBacktestChart = dynamic(
  () => import("@/components/models/charts-recharts").then((m) => m.BallBacktestChart),
  { ssr: false, loading: () => <Placeholder height="h-64" /> },
);
export const OutcomeCalibrationChart = dynamic(
  () => import("@/components/models/charts-recharts").then((m) => m.OutcomeCalibrationChart),
  { ssr: false, loading: () => <Placeholder height="h-72" /> },
);

export function SeriesLegend({ baseline = SERIES.baseline.label }: { baseline?: string }) {
  const labels = { model: SERIES.model.label, baseline };
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Legend">
      {Object.entries(SERIES).map(([key, s]) => (
        <li key={key} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-2 w-4 rounded-full"
            style={{
              background: s.color,
              ...(key === "baseline" ? { opacity: 0.9 } : {}),
            }}
          />
          {labels[key as keyof typeof labels]}
        </li>
      ))}
    </ul>
  );
}
