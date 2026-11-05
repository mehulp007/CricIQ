"use client";

import { ColumnChart } from "@/components/charts/svg/charts";
import { ChartFrame } from "@/components/charts/svg/frame";
import { CHART_THEMES } from "@/components/charts/svg/theme";
import type { OverPoint, PhaseSummary } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { fig, phaseColor } from "@/lib/phases";

const WIDTH = 1200;
const HEIGHT = 520;

/**
 * Runs per over (a Test's ten-over blocks) as columns coloured by phase, with wickets per
 * over as a line on its own scale, and the same figures as a table.
 */
export function OverChart({
  overs,
  phases,
  block,
  competition,
  footer,
}: {
  overs: OverPoint[];
  phases: PhaseSummary[];
  block: number;
  competition: string;
  footer: string;
}) {
  const index = new Map(phases.map((p, i) => [p.key, i]));
  const unit = block === 1 ? "over" : `${block} overs`;
  const title = block === 1 ? "Runs and wickets in each over" : "Runs and wickets by ten overs";
  return (
    <div className="flex flex-col gap-4">
      <ChartFrame
        width={WIDTH}
        height={HEIGHT}
        theme={CHART_THEMES.site}
        title={title}
        subtitle={`${competition}: run rate in each ${unit} (columns, coloured by phase) and wickets per over (line)`}
        footer={footer}
        description={`Run rate and wickets per over for each ${unit}; the figures are in the table below.`}
      >
        {(plot) => (
          <ColumnChart
            plot={plot}
            theme={CHART_THEMES.site}
            frame={{ width: WIDTH, height: HEIGHT }}
            labelEvery={overs.length > 25 ? 5 : 1}
            rows={overs.map((o) => ({
              label: block === 1 ? o.label : String(o.first_over),
              value: o.run_rate,
              display: fig(o.run_rate),
              color: phaseColor(index.get(o.phase) ?? 0),
            }))}
            line={{ label: "Wickets per over", values: overs.map((o) => o.wickets_per_over) }}
          />
        )}
      </ChartFrame>
      <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Phase colours">
        {phases.map((p, i) => (
          <li key={p.key} className="flex items-center gap-1.5">
            <span
              className="inline-block size-2.5 rounded-sm"
              style={{ background: phaseColor(i) }}
              aria-hidden="true"
            />
            {p.label}
          </li>
        ))}
      </ul>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          Show as a table
        </summary>
        <div
          className="relative mt-3 overflow-x-auto"
          {...scrollRegion("Runs and wickets by over")}
        >
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="border-b border-border">
              <tr className="text-xs text-muted-foreground">
                <th scope="col" className="px-2 py-2 text-left font-medium">
                  {block === 1 ? "Over" : "Overs"}
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Innings
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Run rate
                </th>
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Wickets per over
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono tabular-nums">
              {overs.map((o) => (
                <tr key={o.first_over}>
                  <th scope="row" className="px-2 py-1.5 text-left font-normal">
                    {o.label}
                  </th>
                  <td className="px-2 py-1.5 text-right">{o.innings.toLocaleString("en-US")}</td>
                  <td className="px-2 py-1.5 text-right">{fig(o.run_rate)}</td>
                  <td className="px-2 py-1.5 text-right">{fig(o.wickets_per_over)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
