import type { ReactNode } from "react";

import { scrollRegion } from "@/lib/a11y";
import { cn } from "@/lib/utils";

export interface RankedColumn<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Figures align right in tabular digits; text aligns left. */
  numeric?: boolean;
  /** Hidden on phones. */
  wide?: boolean;
}

/** A rank as record tables print it: "=3" when shared. */
export function rankLabel(rank: number, tied: boolean): string {
  return tied ? `=${rank}` : String(rank);
}

/**
 * A ranked list (records, leaders): the rank, then the columns. The first column after
 * the rank stays in view while the rest scroll sideways on a phone.
 */
export function RankedTable<T extends { rank: number; tied: boolean }>({
  label,
  rows,
  columns,
  rowKey,
  className,
}: {
  /** What the table lists, for screen readers and the scroll region. */
  label: string;
  rows: T[];
  columns: RankedColumn<T>[];
  rowKey: (row: T) => string;
  className?: string;
}) {
  const th = "px-3 py-2.5 text-xs font-medium text-muted-foreground";
  return (
    <div
      className={cn("relative overflow-x-auto rounded-2xl border border-border bg-card/70", className)}
      {...scrollRegion(label)}
    >
      <table className="w-full min-w-[32rem] text-sm">
        <caption className="sr-only">{label}</caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "w-12 text-right")}>
              #
            </th>
            {columns.map((column, i) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  th,
                  column.numeric ? "text-right" : "text-left",
                  column.wide && "hidden sm:table-cell",
                  i === 0 && "sticky left-0 bg-card",
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-3 text-right font-mono text-muted-foreground tabular-nums">
                {rankLabel(row.rank, row.tied)}
              </td>
              {columns.map((column, i) => (
                <td
                  key={column.key}
                  className={cn(
                    "px-3 py-3",
                    column.numeric ? "text-right font-mono tabular-nums" : "text-left",
                    column.wide && "hidden sm:table-cell",
                    i === 0 && "sticky left-0 bg-card",
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
