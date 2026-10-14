import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const TONES = {
  default: "text-foreground",
  positive: "text-positive",
  negative: "text-negative",
  primary: "text-primary",
} as const;

/** One headline number: a small label, the value in tabular figures and an optional hint. */
export function StatTile({
  label,
  value,
  hint,
  tone = "default",
  size = "default",
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: keyof typeof TONES;
  size?: "default" | "lg";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 rounded-2xl border border-border bg-card p-4 shadow-elev-1 sm:p-5",
        className,
      )}
    >
      <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </p>
      <p
        className={cn(
          "font-mono font-semibold tracking-tight tabular-nums",
          size === "lg" ? "text-4xl" : "text-2xl sm:text-3xl",
          TONES[tone],
        )}
      >
        {value}
      </p>
      {hint && <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>}
    </div>
  );
}
