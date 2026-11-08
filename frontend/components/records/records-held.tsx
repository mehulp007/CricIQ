import Link from "next/link";

import { Panel } from "@/components/players/profile-parts";
import type { RecordsHeld } from "@/lib/api/types";
import { competitionPath, type CompetitionId } from "@/lib/competitions";
import { recordChartPath } from "@/lib/studio";

function ordinal(n: number): string {
  const tens = n % 100;
  const suffix = tens >= 11 && tens <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th");
  return `${n}${suffix}`;
}

/** A player's places in the top 10 of the competition's record lists. */
export function RecordsHeldPanel({
  held,
  competition,
}: {
  held: RecordsHeld;
  competition: CompetitionId;
}) {
  return (
    <Panel
      id="records-held"
      title="Records held"
      lede="Places in the top 10 of the competition's record lists, in its ball-by-ball data. Equal figures share a rank."
    >
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {held.records.map(({ record, entries }) => {
          const best = entries[0];
          const chart = recordChartPath(record.key);
          return (
            <li
              key={record.key}
              className="flex min-w-0 flex-col gap-1.5 rounded-xl border border-border bg-card/60 p-4"
            >
              <Link
                href={competitionPath(competition, `/records/${record.key}`)}
                prefetch={false}
                className="truncate text-sm font-medium underline-offset-4 hover:text-primary hover:underline"
              >
                {record.label}
              </Link>
              <p className="flex items-baseline gap-2">
                <span className="font-mono text-2xl font-semibold tabular-nums">
                  {best.display}
                </span>
                <span className="text-sm text-muted-foreground">
                  {best.rank === 1
                    ? best.tied
                      ? "Equals the record"
                      : "The record"
                    : `${best.tied ? "=" : ""}${ordinal(best.rank)}`}
                </span>
              </p>
              {entries.length > 1 && (
                <p className="text-xs text-muted-foreground">
                  {entries.length} entries in the top 10
                </p>
              )}
              {record.model && <p className="text-xs text-muted-foreground">Model estimate</p>}
              {chart && (
                <Link
                  href={competitionPath(competition, chart)}
                  prefetch={false}
                  className="text-xs text-primary underline-offset-4 hover:underline"
                >
                  Make a chart of this list
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
