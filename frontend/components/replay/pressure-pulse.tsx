import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/**
 * How fast and how bright the glow breathes for the pressure on the next ball (its 0–100
 * percentile of leverage): a slow, faint 4s at rest, quickening above the 75th percentile to a
 * 1.2s beat at the very top. Never faster than about one beat a second.
 */
export function pulseFor(pressure: number): { speed: number; intensity: number } {
  const p = Math.min(Math.max(pressure, 0), 100);
  const speed = p >= 75 ? 1.8 - ((p - 75) / 25) * 0.6 : 4 - (p / 75) * 1.6;
  return { speed: Math.round(speed * 100) / 100, intensity: Math.round(6 + (p / 100) * 12) };
}

/**
 * A glow ring around the win-probability bar that breathes with the pressure on the next ball,
 * like a heart-rate trace: calm when little hangs on it, quick when the match is in the balance.
 * Decorative (the pressure panel says the same in words); still for reduced motion.
 */
export function PressurePulse({
  pressure,
  className,
}: {
  pressure: number | null;
  className?: string;
}) {
  if (pressure === null) return null;
  const { speed, intensity } = pulseFor(pressure);
  return (
    <span
      aria-hidden="true"
      data-pressure={Math.round(pressure)}
      className={cn("pressure-pulse pointer-events-none absolute -inset-1 rounded-full", className)}
      style={{ "--pulse-speed": `${speed}s`, "--pulse-intensity": intensity } as CSSProperties}
    />
  );
}
