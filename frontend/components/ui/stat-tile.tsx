import type { ReactNode } from "react";

import { CountUp } from "@/components/ui/count-up";
import { Reveal } from "@/components/ui/stagger-grid";
import { cn } from "@/lib/utils";

const TONES = {
  default: "text-foreground",
  positive: "text-positive",
  negative: "text-negative",
  primary: "text-primary",
} as const;

// A plain figure: an optional sign, digits with grouping commas and decimals, an optional "%".
const FIGURE = /^[+−-]?\d{1,3}(?:,\d{2,3})*(?:\.\d+)?%?$|^[+−-]?\d+(?:\.\d+)?%?$/;

/** A figure counts up as it scrolls into view; anything else fades in. */
function Value({ value }: { value: ReactNode }) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return <CountUp value={value} text={String(value)} />;
  }
  if (typeof value === "string" && FIGURE.test(value)) {
    return <CountUp value={Number(value.replace(/[^\d.]/g, ""))} text={value} />;
  }
  return <Reveal>{value}</Reveal>;
}

/** One headline number: a small label, the value in tabular figures and an optional hint. */
export function StatTile({
  label,
  value,
  unit,
  hint,
  tone = "default",
  size = "default",
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  /** A unit after the value ("runs"), in small text. */
  unit?: ReactNode;
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
        <Value value={value} />
        {unit && (
          <span className="ml-1.5 font-sans text-sm font-normal text-muted-foreground">{unit}</span>
        )}
      </p>
      {hint && <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>}
    </div>
  );
}
