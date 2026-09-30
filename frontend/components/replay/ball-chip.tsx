import type { TimelineDelivery } from "@/lib/api/types";
import { ballChip } from "@/lib/replay/engine";
import { cn } from "@/lib/utils";

/** One delivery as a compact chip. Colour is secondary; the label carries meaning. */
export function BallChip({
  delivery,
  className,
}: {
  delivery: TimelineDelivery;
  className?: string;
}) {
  const label = ballChip(delivery);
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
        "inline-grid h-7 min-w-7 place-items-center rounded-full px-1.5 font-mono text-xs font-semibold tabular-nums",
        tone,
        className,
      )}
      title={delivery.ball_label ? `Ball ${delivery.ball_label}` : undefined}
    >
      {label}
    </span>
  );
}
