import type { GroundPhases, PhaseSummary } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { fig } from "@/lib/phases";

/** Run rate by phase at the busiest grounds, worked out from the balls bowled there. */
export function GroundsTable({
  grounds,
  phases,
}: {
  grounds: GroundPhases[];
  phases: PhaseSummary[];
}) {
  return (
    <div className="relative overflow-x-auto" {...scrollRegion("Run rate by phase at each ground")}>
      <table className="w-full min-w-[34rem] text-sm">
        <thead className="border-b border-border">
          <tr className="text-xs text-muted-foreground">
            <th scope="col" className="sticky left-0 bg-card px-2 py-2 text-left font-medium">
              Ground
            </th>
            <th scope="col" className="px-2 py-2 text-right font-medium">
              Matches
            </th>
            {phases.map((p) => (
              <th key={p.key} scope="col" className="px-2 py-2 text-right font-medium">
                {p.label} RR
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {grounds.map((g) => {
            const rate = new Map(g.phases.map((p) => [p.phase, p.run_rate]));
            return (
              <tr key={g.venue_id}>
                <th
                  scope="row"
                  className="sticky left-0 max-w-[14rem] bg-card px-2 py-2 text-left font-normal"
                >
                  <span className="block truncate">{g.name}</span>
                  {g.city && (
                    <span className="block truncate text-xs text-muted-foreground">{g.city}</span>
                  )}
                </th>
                <td className="px-2 py-2 text-right font-mono tabular-nums">{g.matches}</td>
                {phases.map((p) => (
                  <td key={p.key} className="px-2 py-2 text-right font-mono tabular-nums">
                    {fig(rate.get(p.key) ?? null)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
