import { Info } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Timeline } from "@/lib/api/types";
import { formatPercent } from "@/lib/replay/win-probability";

/** Chart roles, as in the worm: side batting first = team A, chasing side = team B. */
export const SIDE_COLORS = { a: "var(--team-a)", b: "var(--team-b)" } as const;

export function ModelEstimateNote() {
  return (
    <Tooltip>
      <TooltipTrigger
        className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
        aria-label="About this estimate"
      >
        <Info className="size-3" aria-hidden="true" />
        Model estimate
      </TooltipTrigger>
      <TooltipContent className="max-w-64 leading-relaxed">
        A calibrated estimate from how thousands of IPL matches in similar situations turned out. It
        is not a prediction of this match and not betting advice.
      </TooltipContent>
    </Tooltip>
  );
}

export function WinProbabilityBar({ timeline, wp }: { timeline: Timeline; wp: number | null }) {
  if (wp === null) return null;
  const { team_a, team_b } = timeline.summary;
  const a = Math.round(wp * 1000) / 10;
  const label = `Win probability: ${team_a.name} ${formatPercent(wp)}, ${team_b.name} ${formatPercent(1 - wp)}`;

  return (
    <div className="mt-5 flex flex-col gap-2" data-testid="win-probability">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] tracking-wide text-muted-foreground uppercase">
          Win probability
        </span>
        <ModelEstimateNote />
      </div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="size-2 rounded-full"
            style={{ background: SIDE_COLORS.a }}
          />
          {team_a.franchise_id}
          <span className="font-mono text-base font-semibold tabular-nums">
            {formatPercent(wp)}
          </span>
        </span>
        <span className="flex items-center gap-2">
          <span className="font-mono text-base font-semibold tabular-nums">
            {formatPercent(1 - wp)}
          </span>
          {team_b.franchise_id}
          <span
            aria-hidden="true"
            className="size-2 rounded-full"
            style={{ background: SIDE_COLORS.b }}
          />
        </span>
      </div>
      <div role="img" aria-label={label} className="flex h-2 gap-0.5 overflow-hidden rounded-full">
        <span
          className="h-full rounded-l-full transition-[width] duration-500 ease-out"
          style={{ width: `${a}%`, background: SIDE_COLORS.a }}
        />
        <span className="h-full flex-1 rounded-r-full" style={{ background: SIDE_COLORS.b }} />
      </div>
    </div>
  );
}
