import Link from "next/link";

import { CompetitionLink } from "@/components/competition/competition-link";
import { Panel } from "@/components/players/profile-parts";
import { SeriesCard } from "@/components/series/series-card";
import { getHeadToHead, getSeriesRecord } from "@/lib/api/client";
import type { HeadToHead, SeriesRecord } from "@/lib/api/types";
import { scrollRegion } from "@/lib/a11y";
import { COMPETITIONS, competitionPath, type CompetitionId } from "@/lib/competitions";
import { cn } from "@/lib/utils";

const SHOWN_SERIES = 6;

interface FormatLine {
  competition: CompetitionId;
  label: string;
  h2h: HeadToHead | null;
  series: SeriesRecord | null;
}

async function line(competition: CompetitionId, a: string, b: string): Promise<FormatLine> {
  const [h2h, series] = await Promise.all([
    getHeadToHead(competition, a, b).catch(() => null),
    getSeriesRecord(competition, a, b).catch(() => null),
  ]);
  const label = COMPETITIONS.find((c) => c.id === competition)!.label;
  return { competition, label, h2h, series };
}

/**
 * Two national sides in every international format: their meetings and their series,
 * each format's record kept apart, with this format's series listed below.
 */
export async function AcrossFormats({
  competition,
  a,
  b,
}: {
  competition: CompetitionId;
  a: string;
  b: string;
}) {
  const formats = COMPETITIONS.filter((c) => c.teamType === "national").map((c) => c.id);
  const lines = (await Promise.all(formats.map((c) => line(c, a, b)))).filter(
    (l) => l.h2h !== null && l.h2h.record.played > 0,
  );
  if (lines.length === 0) return null;
  const here = lines.find((l) => l.competition === competition)?.series ?? null;
  const names = lines[0].h2h!;
  const th = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
  const cell = "px-3 py-2 text-right font-mono tabular-nums";
  return (
    <Panel
      id="formats"
      title="In every format"
      lede={`${names.a.name} and ${names.b.name}'s meetings and series in each international format, each counted on its own. A series counts once it has two or more matches and is over.`}
    >
      <div className="overflow-x-auto" {...scrollRegion("Record in every format")}>
        <table className="w-full min-w-[34rem] text-sm">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                Format
              </th>
              <th scope="col" className={th}>
                Meetings
              </th>
              <th scope="col" className={th}>
                {names.a.franchise_id} won
              </th>
              <th scope="col" className={th}>
                {names.b.franchise_id} won
              </th>
              <th scope="col" className={th}>
                Drawn, tied or no result
              </th>
              <th scope="col" className={th}>
                Series ({names.a.franchise_id}–{names.b.franchise_id}–level)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {lines.map((l) => {
              const r = l.h2h!.record;
              const other = r.played - r.a_won - r.b_won;
              const s = l.series;
              return (
                <tr
                  key={l.competition}
                  className={cn(l.competition === competition && "bg-muted/40")}
                >
                  <th scope="row" className="px-3 py-2 text-left font-medium">
                    <Link
                      href={competitionPath(l.competition, `/teams/h2h?a=${a}&b=${b}`)}
                      className="underline-offset-4 hover:text-primary hover:underline"
                    >
                      {l.label}
                    </Link>
                  </th>
                  <td className={cell}>{r.played}</td>
                  <td className={cell}>{r.a_won}</td>
                  <td className={cell}>{r.b_won}</td>
                  <td className={cell}>{other}</td>
                  <td className={cell}>
                    {s && s.played > 0 ? `${s.a_won}–${s.b_won}–${s.drawn}` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {here && here.series.length > 0 && (
        <div className="mt-6 flex flex-col gap-3">
          <h3 className="text-sm font-medium">Their latest series and tournaments here</h3>
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {here.series.slice(0, SHOWN_SERIES).map((s) => (
              <li key={s.event_id} className="flex">
                <SeriesCard competition={competition} series={s} />
              </li>
            ))}
          </ul>
          {here.series.length > SHOWN_SERIES && (
            <CompetitionLink
              href={`/series?team=${a}`}
              className="text-sm text-primary underline-offset-4 hover:underline"
            >
              More series
            </CompetitionLink>
          )}
        </div>
      )}
    </Panel>
  );
}
