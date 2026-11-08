import Link from "next/link";
import type { ReactNode } from "react";

import { scrollRegion } from "@/lib/a11y";
import { COMPETITIONS } from "@/lib/competitions";

/**
 * About & Methodology for the analysis tools: phases, records, Chart Studio, On This Day and
 * the daily notes. Every definition here is the one the pipeline or the API uses
 * (config/phases.yaml, config/records.yaml, criciq_core.stats, criciq_pipelines.notes).
 */

const PHASES = [
  { format: "T20", phases: "Powerplay 1–6 · Middle overs 7–15 · Death overs 16–20", leaders: 60 },
  {
    format: "ODI",
    phases: "Powerplay 1–10 · Middle overs 11–40 · Death overs 41–50",
    leaders: 120,
  },
  {
    format: "Test",
    phases: "New ball 1–20 · Middle overs 21–80 · Second new ball 81 on",
    leaders: 300,
  },
];

const QUALIFY = [
  { format: "T20", average: 20, sr: 500, innings: 20, economy: 300, spell: "24 (four overs)" },
  {
    format: "ODI",
    average: 20,
    sr: "1,000",
    innings: 30,
    economy: "1,000",
    spell: "48 (eight overs)",
  },
  { format: "Test", average: 20, sr: "2,000", innings: 50, economy: "2,000", spell: "none" },
];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="text-xl font-semibold tracking-tight">
        {title}
      </h2>
      <div className="flex flex-col gap-3 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

function Strong({ children }: { children: ReactNode }) {
  return <span className="font-medium text-foreground">{children}</span>;
}

function Table({
  label,
  head,
  rows,
}: {
  label: string;
  head: string[];
  rows: (string | number)[][];
}) {
  return (
    <div
      className="relative overflow-x-auto rounded-xl border border-border"
      {...scrollRegion(label)}
    >
      <table className="w-full min-w-[32rem] text-sm">
        <thead className="border-b border-border bg-muted/40">
          <tr className="text-xs text-muted-foreground">
            {head.map((h, i) => (
              <th
                key={h}
                scope="col"
                className={`px-3 py-2 font-medium ${i ? "text-right" : "text-left"}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={String(row[0])}>
              {row.map((cell, i) =>
                i === 0 ? (
                  <th
                    key={i}
                    scope="row"
                    className="px-3 py-2 text-left font-medium text-foreground"
                  >
                    {cell}
                  </th>
                ) : (
                  <td key={i} className="px-3 py-2 text-right font-mono tabular-nums">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ToolSections() {
  return (
    <>
      <Section id="phases" title="Phases: how innings are built">
        <p>
          Every ball belongs to a phase of its innings, by format. A batter faces every ball but a
          wide; a bowler concedes the batter&apos;s runs, wides and no-balls; a batter&apos;s
          dismissals include run outs, a bowler&apos;s wickets only those credited to the bowler.
          Super overs are left out. A phase leader needs a minimum of balls in that phase (fewer in
          a competition with under 50 matches).
        </p>
        <Table
          label="Phases by format"
          head={["Format", "Phases (overs)", "Leaders need"]}
          rows={PHASES.map((p) => [p.format, p.phases, `${p.leaders} balls`])}
        />
        <p>
          Run rates by ground are worked out from the balls bowled there. CricIQ has no pitch,
          weather or ball-tracking data, so a ground&apos;s figures describe what happened there,
          not why.
        </p>
      </Section>

      <Section id="records" title="Records: the ball-by-ball era">
        <p>
          Records count only the matches in CricIQ&apos;s ball-by-ball data, so a record set before
          a competition&apos;s data begins is not there, and every records page says which seasons
          it covers. Equal figures share a rank (=3). Partnerships are worked out ball by ball (a
          retired-hurt batter starts a new stand for the same wicket); the fastest fifties and
          hundreds count balls faced, wides excluded; the biggest win-probability swing and the
          highest win probability added are <Strong>model estimates</Strong>.
        </p>
        <Table
          label="Where each competition's data begins"
          head={["Competition", "Ball-by-ball data from"]}
          rows={COMPETITIONS.map((c) => [
            c.label,
            c.spansNewYear
              ? `${c.firstSeason - 1}/${String(c.firstSeason % 100).padStart(2, "0")}`
              : c.firstSeason,
          ])}
        />
        <p>Averages and rates need enough of a career that one good day can&apos;t top the list:</p>
        <Table
          label="Record qualifications"
          head={[
            "Format",
            "Averages (innings or wickets)",
            "Career strike rate and economy (balls)",
            "Strike rate in an innings (balls)",
            "Economy in an innings (balls)",
          ]}
          rows={QUALIFY.map((q) => [
            q.format,
            q.average,
            `${q.sr} · ${q.economy}`,
            q.innings,
            q.spell,
          ])}
        />
      </Section>

      <Section id="studio" title="Chart Studio">
        <p>
          <Link href="/ipl/studio" className="text-primary underline-offset-4 hover:underline">
            Chart Studio
          </Link>{" "}
          builds a chart from six datasets: batting and bowling innings, batting and bowling by
          phase, careers (each player&apos;s matches, with fielding and win probability added) and
          team results. Its measures use the same definitions as every page: batting average is runs
          per dismissal, strike rate runs per 100 balls faced, economy runs per six legal balls,
          bowling average runs per wicket and bowling strike rate balls per wicket; dot and boundary
          percentages are shares of balls. <Strong>Runs above par</Strong> is what a batter made
          beyond an average batter of the same competition from the same balls (same season and
          phase), <Strong>runs saved</Strong> the bowling equivalent, and win probability added a
          model estimate. Team totals and run rates are left out for Tests, whose team table holds
          the first innings only.
        </p>
        <p>
          A chart is a spec checked against a fixed list of datasets, measures and groupings, never
          SQL from the browser; it runs as one query with every value passed separately, shown in
          the SQL tab, with a 10-second limit and at most 50 rows and eight series. Equal figures
          share a rank. A picture you add stays in your browser, and a saved design is kept only
          there; a link carries everything else.
        </p>
      </Section>

      <Section id="on-this-day" title="On this day">
        <p>
          On this day lists every match that started on the date in any year, across all eight
          competitions, most notable first. A final adds 3, another playoff 2, a hundred 3 (a fifty
          1), a five-wicket haul 3 (four wickets 1), and a ball that moved a side&apos;s chance of
          winning by 50 points or more 1. Today&apos;s page uses India&apos;s date on the server and
          moves to your own date in the browser if it differs.
        </p>
      </Section>

      <Section id="notes" title="Daily notes: how they are written">
        <p>
          A{" "}
          <Link href="/notes" className="text-primary underline-offset-4 hover:underline">
            daily note
          </Link>{" "}
          is written for every day a match ended, from CricIQ&apos;s own data and nothing else: no
          news source, and no model writes any text. Each sentence comes from a fixed rule, and
          every figure in it is read from the tables, so the same data always gives the same note.
          For each match it gives:
        </p>
        <ul className="ml-5 list-disc space-y-1">
          <li>
            the result, with the innings totals, the best batting and bowling and the player of the
            match;
          </li>
          <li>
            the ball with the biggest change in win probability (when it moved a side by 10 points
            or more) and the player who added the most win probability, both{" "}
            <Strong>model estimates</Strong>;
          </li>
          <li>
            milestones within the competition&apos;s data: runs at every 1,000 (500 in the leagues),
            wickets and matches at every 50, leaving out international players whose careers may
            have begun before the data;
          </li>
          <li>
            a total, score, stand or bowling figures that went into the top 10 of the
            competition&apos;s data so far, once it has 30 matches;
          </li>
          <li>
            a league side&apos;s place in the table worked out from the results, or a series score.
          </li>
        </ul>
        <p>
          Notes are rebuilt with every data update. Cricsheet publishes matches a day or two after
          play, so a day&apos;s note appears then; a note&apos;s date is the day its matches ended,
          and it shows when its newest match came into the data.
        </p>
      </Section>
    </>
  );
}
