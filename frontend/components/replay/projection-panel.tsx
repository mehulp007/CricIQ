import { ModelEstimateNote, SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import { formatPercent } from "@/lib/replay/win-probability";
import { probabilityAtLeast, projectionAt, thresholdsFor } from "@/lib/replay/projection";

/** Projected first-innings total: median, 80% range and the odds of passing round totals. */
export function ProjectionPanel({ timeline, cursor }: { timeline: Timeline; cursor: number }) {
  const projection = projectionAt(timeline, cursor);
  if (!projection) return null;
  const batting = timeline.summary.team_a;
  const thresholds = thresholdsFor(projection);

  return (
    <section
      aria-label="Projected total"
      className="rounded-2xl border border-border bg-card/70 p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xs tracking-wide text-muted-foreground uppercase">
          Projected total · {batting.franchise_id}
        </h2>
        <ModelEstimateNote />
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="font-mono text-4xl font-semibold tracking-tight tabular-nums">
          {projection.median}
        </span>
        <span className="text-sm text-muted-foreground">
          80% range{" "}
          <span className="font-mono text-foreground tabular-nums">
            {projection.low}–{projection.high}
          </span>
        </span>
      </div>

      {thresholds.length > 0 && (
        <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          {thresholds.map((total) => {
            const p = probabilityAtLeast(projection, total);
            return (
              <li key={total} className="flex flex-col gap-1.5">
                <span className="flex items-baseline justify-between text-xs text-muted-foreground">
                  {total}+
                  <span className="font-mono text-sm text-foreground tabular-nums">
                    {formatPercent(p)}
                  </span>
                </span>
                <span
                  className="h-1.5 rounded-full bg-muted"
                  role="img"
                  aria-label={`${formatPercent(p)} chance of ${total} or more`}
                >
                  <span
                    className="block h-full rounded-full transition-[width] duration-500 ease-out"
                    style={{ width: `${p * 100}%`, background: SIDE_COLORS.a }}
                  />
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
