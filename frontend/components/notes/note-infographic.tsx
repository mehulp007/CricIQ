"use client";

import { Download } from "lucide-react";
import { useRef, useState } from "react";

import { HeadlineNumber, TableCard } from "@/components/charts/svg/charts";
import { ChartFrame } from "@/components/charts/svg/frame";
import { CHART_SIZES, CHART_THEMES } from "@/components/charts/svg/theme";
import { Button } from "@/components/ui/button";
import type { Note } from "@/lib/api/types";
import { downloadPng } from "@/lib/export-image";
import { competitionLabel, noteDateLabel } from "@/lib/notes";

const SIZE = CHART_SIZES.landscape;
const THEME = CHART_THEMES.dark;

/** The day in one image: two headline figures and the standout performers with their
 * totals in the competition's data before and after the match. */
export function NoteInfographic({ note }: { note: Note }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [status, setStatus] = useState("");
  const top = note.figures[0];
  const title = `${noteDateLabel(note.date)} in numbers`;
  const footer = `Data: Cricsheet (ODC-BY 1.0) · data ${note.data_version}`;
  const rows = note.figures.map((f) => [
    f.name,
    competitionLabel(f.competition),
    f.figure,
    `${f.career_before.toLocaleString("en-US")} ${f.unit}`,
    `${f.career_after.toLocaleString("en-US")} ${f.unit}`,
  ]);
  return (
    <div className="flex flex-col gap-3">
      <ChartFrame
        width={SIZE.width}
        height={SIZE.height}
        theme={THEME}
        title={title}
        subtitle={`${note.match_count} ${note.match_count === 1 ? "match" : "matches"} · career totals in CricIQ's data, before and after`}
        footer={footer}
        description={`${title}: the day's standout figures; they are listed in the note below.`}
        svgRef={svgRef}
      >
        {(plot) => {
          const head = { ...plot, height: plot.height * 0.3 };
          const table = {
            ...plot,
            y: plot.y + plot.height * 0.36,
            height: plot.height * 0.64,
          };
          return (
            <>
              <HeadlineNumber
                plot={head}
                theme={THEME}
                frame={SIZE}
                items={[
                  {
                    label: note.match_count === 1 ? "match" : "matches",
                    value: String(note.match_count),
                  },
                  ...(top ? [{ label: top.name, value: top.figure }] : []),
                ]}
              />
              <TableCard
                plot={table}
                theme={THEME}
                frame={SIZE}
                columns={[
                  { header: "Player" },
                  { header: "Competition", numeric: false },
                  { header: "In the match", numeric: true },
                  { header: "Before", numeric: true },
                  { header: "After", numeric: true },
                ]}
                rows={rows}
              />
            </>
          );
        }}
      </ChartFrame>
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="lg"
          onClick={async () => {
            if (!svgRef.current) return;
            try {
              await downloadPng(svgRef.current, `criciq-notes-${note.date}`);
              setStatus("Saved the PNG.");
            } catch {
              setStatus("This browser couldn't make the image.");
            }
          }}
        >
          <Download aria-hidden="true" />
          Download PNG
        </Button>
        <span className="text-xs text-muted-foreground" role="status" aria-live="polite">
          {status}
        </span>
      </div>
    </div>
  );
}
