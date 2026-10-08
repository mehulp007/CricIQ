import { CompetitionLink } from "@/components/competition/competition-link";
import { TeamSwatch } from "@/components/match/team-badge";
import type { SeriesStanding } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { cn } from "@/lib/utils";

function nrr(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(3)}`;
}

/** A tournament round's table: two points a win, one a tie or no result, then net run rate. */
export function StandingsTable({ rows, label }: { rows: SeriesStanding[]; label: string }) {
  const th = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
  const cell = "px-3 py-2 text-right font-mono tabular-nums";
  const tied = rows.some((r) => r.tied > 0);
  const noResult = rows.some((r) => r.no_result > 0);
  return (
    <div className="overflow-x-auto rounded-xl border border-border" {...scrollRegion(label)}>
      <table className="w-full min-w-[30rem] text-sm">
        <caption className="sr-only">{label}</caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "w-10")}>
              <span className="sr-only">Position</span>
            </th>
            <th scope="col" className={cn(th, "text-left")}>
              Side
            </th>
            <th scope="col" className={th}>
              <abbr title="Played">P</abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Won">W</abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Lost">L</abbr>
            </th>
            {tied && (
              <th scope="col" className={th}>
                <abbr title="Tied">T</abbr>
              </th>
            )}
            {noResult && (
              <th scope="col" className={th}>
                <abbr title="No result">NR</abbr>
              </th>
            )}
            <th scope="col" className={th}>
              <abbr title="Points">Pts</abbr>
            </th>
            <th scope="col" className={th}>
              <abbr title="Net run rate">NRR</abbr>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={r.team.franchise_id}>
              <td className={cn(cell, "text-muted-foreground")}>{r.position}</td>
              <th scope="row" className="px-3 py-2 text-left font-normal">
                <CompetitionLink
                  href={`/teams/${r.team.franchise_id}`}
                  className="inline-flex items-center gap-2 underline-offset-4 hover:text-primary hover:underline"
                >
                  <TeamSwatch color={r.team.color} />
                  {r.team.name}
                </CompetitionLink>
              </th>
              <td className={cell}>{r.played}</td>
              <td className={cell}>{r.won}</td>
              <td className={cell}>{r.lost}</td>
              {tied && <td className={cell}>{r.tied}</td>}
              {noResult && <td className={cell}>{r.no_result}</td>}
              <td className={cn(cell, "font-semibold text-foreground")}>{r.points}</td>
              <td className={cell}>{nrr(r.nrr)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
