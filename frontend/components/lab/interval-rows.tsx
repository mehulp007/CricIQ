import type { Estimate } from "@/lib/lab";
import { signed } from "@/lib/lab";

export interface IntervalRow {
  label: string;
  detail?: string;
  estimate: Estimate;
}

/**
 * Estimates with 90% intervals on a shared axis around zero. A row whose
 * interval crosses the zero line is not distinguishable from "no effect".
 */
export function IntervalRows({
  rows,
  unit,
  digits = 1,
  color = "var(--chart-3)",
  caption,
}: {
  rows: IntervalRow[];
  unit: string;
  digits?: number;
  color?: string;
  caption: string;
}) {
  const reach =
    Math.max(...rows.flatMap((r) => [Math.abs(r.estimate.low), Math.abs(r.estimate.high)]), 1e-9) *
    1.1;
  const pos = (v: number) => 50 + (v / reach) * 50;
  return (
    <figure className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {rows.map((r) => {
          const { value, low, high } = r.estimate;
          return (
            <li
              key={r.label}
              className="grid grid-cols-[minmax(0,1fr)_7rem] items-center gap-x-3 gap-y-1 sm:grid-cols-[11rem_minmax(0,1fr)_7rem]"
            >
              <span className="col-span-2 text-sm sm:col-span-1">
                {r.label}
                {r.detail && (
                  <span className="block text-xs text-muted-foreground">{r.detail}</span>
                )}
              </span>
              <span
                className="relative block h-4"
                role="img"
                aria-label={`${r.label}: ${signed(value, digits)} ${unit}, 90% interval ${signed(low, digits)} to ${signed(high, digits)}`}
              >
                <span
                  aria-hidden="true"
                  className="absolute -inset-y-0.5 w-px bg-foreground/40"
                  style={{ left: "50%" }}
                />
                <span
                  aria-hidden="true"
                  className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full opacity-40"
                  style={{
                    left: `${pos(low)}%`,
                    width: `${Math.max(pos(high) - pos(low), 0.5)}%`,
                    background: color,
                  }}
                />
                <span
                  aria-hidden="true"
                  className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
                  style={{ left: `${pos(value)}%`, background: color }}
                />
              </span>
              <span className="text-right font-mono text-sm tabular-nums">
                {signed(value, digits)}
                <span className="block text-[11px] text-muted-foreground">
                  {signed(low, digits)} to {signed(high, digits)}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <figcaption className="text-xs leading-relaxed text-muted-foreground">{caption}</figcaption>
    </figure>
  );
}
