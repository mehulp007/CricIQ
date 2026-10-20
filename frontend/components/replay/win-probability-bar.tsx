"use client";

import { Info } from "lucide-react";
import { m } from "motion/react";

import { PressurePulse } from "@/components/replay/pressure-pulse";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePrefersReducedMotion } from "@/lib/animation";
import type { Timeline } from "@/lib/api/types";
import { formatPercent } from "@/lib/replay/win-probability";
import { cn } from "@/lib/utils";

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
        A calibrated estimate from how thousands of matches in similar situations turned out. It is
        not a prediction of this match and not betting advice.
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Each side's chance of winning as a two-colour bar. The split moves on a spring as the replay
 * steps (it picks up its speed rather than restarting when balls come quickly), the leading edge
 * of team A's share is lit, a dashed line marks even money, and a glow around the bar breathes
 * with the pressure on the next ball.
 */
export function WinProbabilityBar({
  timeline,
  wp,
  pressure = null,
}: {
  timeline: Timeline;
  wp: number | null;
  /** The pressure on the next ball (0–100), for the glow; none once the match is over. */
  pressure?: number | null;
}) {
  const reduced = usePrefersReducedMotion();
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
      <div className="relative">
        <PressurePulse pressure={pressure} />
        <div
          role="img"
          aria-label={label}
          className={cn(
            "relative flex h-3 overflow-hidden rounded-full shadow-inner",
            a > 0 && a < 100 && "gap-0.5",
          )}
        >
          <m.span
            initial={false}
            animate={{ width: `${a}%` }}
            transition={
              reduced ? { duration: 0 } : { type: "spring", stiffness: 160, damping: 24, mass: 0.8 }
            }
            className="relative h-full shrink-0 after:absolute after:inset-y-0 after:right-0 after:w-6 after:max-w-full after:bg-linear-to-l after:from-white/50 after:to-transparent"
            style={{ background: SIDE_COLORS.a }}
          />
          <span className="h-full min-w-0 flex-1" style={{ background: SIDE_COLORS.b }} />
        </div>
        {/* Even money. */}
        <span
          aria-hidden="true"
          className="absolute -inset-y-1 left-1/2 w-0 -translate-x-1/2 border-l border-dashed border-foreground/60"
        />
      </div>
    </div>
  );
}
