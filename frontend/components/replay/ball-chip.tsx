"use client";

import { m } from "motion/react";

import type { TimelineDelivery } from "@/lib/api/types";
import { ballChip } from "@/lib/replay/engine";
import { cn } from "@/lib/utils";

/** The colour a wicket, six or four flashes as it arrives in the feed. */
function flashColor(delivery: TimelineDelivery): string | null {
  if (delivery.wicket?.is_dismissal) return "var(--wicket)";
  if (delivery.is_six) return "var(--six)";
  if (delivery.is_four) return "var(--boundary)";
  return null;
}

/**
 * One delivery as a compact chip. Colour is secondary; the label carries meaning.
 *
 * With `flash`, a wicket, six or four sends out one ring of its colour as the chip first appears
 * (only then: a chip already on screen never flashes again). Reduced motion keeps just a fade.
 */
export function BallChip({
  delivery,
  flash = false,
  className,
}: {
  delivery: TimelineDelivery;
  flash?: boolean;
  className?: string;
}) {
  const label = ballChip(delivery);
  const ring = flashColor(delivery);
  const tone = delivery.wicket?.is_dismissal
    ? "bg-wicket text-background"
    : delivery.is_six
      ? "bg-six text-background"
      : delivery.is_four
        ? "bg-boundary text-background"
        : delivery.wides || delivery.noballs
          ? "border border-team-b/60 text-team-b"
          : delivery.runs_total === 0
            ? "border border-border text-muted-foreground"
            : "border border-border text-foreground";
  return (
    <span
      className={cn(
        "relative inline-grid h-7 min-w-7 place-items-center rounded-full px-1.5 font-mono text-xs font-semibold tabular-nums",
        tone,
        className,
      )}
      title={delivery.ball_label ? `Ball ${delivery.ball_label}` : undefined}
    >
      {ring && (
        <m.span
          aria-hidden="true"
          data-flash=""
          className="pointer-events-none absolute inset-0 rounded-full"
          style={{ boxShadow: `0 0 0 2px ${ring}, 0 0 14px 2px ${ring}` }}
          initial={flash ? { opacity: 0.9, scale: 1 } : false}
          animate={{ opacity: 0, scale: 2.2 }}
          transition={{ duration: 0.65, ease: "easeOut" }}
        />
      )}
      {label}
    </span>
  );
}
