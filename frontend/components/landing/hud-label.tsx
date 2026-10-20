import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/**
 * A telemetry-style label. On wide screens it floats beside the particle ball, `dx` and `dy` ball
 * radii from its centre (the stage's `--ball-*` variables, shared with the canvas); on phones the
 * labels sit in a row. Dark glass, monospace figures.
 */
export function HudLabel({
  label,
  value,
  dx,
  dy,
  delay = 0,
  className,
}: {
  label: string;
  value: string;
  dx: number;
  dy: number;
  delay?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "landing-hud landing-glass landing-fade flex flex-col gap-0.5 rounded-xl px-3 py-2 font-mono",
        className,
      )}
      style={{ "--dx": dx, "--dy": dy, "--delay": `${700 + delay}ms` } as CSSProperties}
    >
      <span className="flex items-center gap-1.5 text-[10px] tracking-[0.18em] text-white/65 uppercase">
        <span className="size-1.5 rounded-full bg-neon-turf shadow-[0_0_8px_var(--neon-turf)]" />
        {label}
      </span>
      <span className="text-base font-semibold text-white tabular-nums sm:text-lg">{value}</span>
    </div>
  );
}
