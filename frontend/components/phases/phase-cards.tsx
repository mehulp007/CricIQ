import type { PhaseSummary } from "@/lib/api/types";
import { fig, oversLabel, phaseColor } from "@/lib/phases";

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="font-mono text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** One card per phase: how fast runs came, how often wickets fell, boundaries and dots. */
export function PhaseCards({ phases }: { phases: PhaseSummary[] }) {
  return (
    <ul className="grid grid-cols-1 gap-3 md:grid-cols-3" aria-label="Phases">
      {phases.map((phase, i) => (
        <li
          key={phase.key}
          className="flex min-w-0 flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="flex items-center gap-2 font-semibold tracking-tight">
                <span
                  className="inline-block size-2.5 shrink-0 rounded-full"
                  style={{ background: phaseColor(i) }}
                  aria-hidden="true"
                />
                {phase.label}
              </h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {oversLabel(phase.first_over, phase.last_over)} ·{" "}
                {phase.innings.toLocaleString("en-US")} innings
              </p>
            </div>
            <p className="text-right">
              <span className="block font-mono text-3xl font-semibold tabular-nums">
                {fig(phase.run_rate)}
              </span>
              <span className="text-[11px] tracking-wide text-muted-foreground uppercase">
                Run rate
              </span>
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 md:grid-cols-2 xl:grid-cols-3">
            <Figure label="Runs / innings" value={fig(phase.runs_per_innings, 1)} />
            <Figure label="Wickets / innings" value={fig(phase.wickets_per_innings)} />
            <Figure label="Balls / wicket" value={fig(phase.balls_per_wicket, 1)} />
            <Figure label="Boundary %" value={fig(phase.boundary_pct, 1)} />
            <Figure label="Dot %" value={fig(phase.dot_pct, 1)} />
            <Figure label="Sixes" value={phase.sixes.toLocaleString("en-US")} />
          </dl>
        </li>
      ))}
    </ul>
  );
}
