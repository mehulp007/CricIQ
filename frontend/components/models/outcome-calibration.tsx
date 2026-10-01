"use client";

import { useState } from "react";

import { OutcomeCalibrationChart } from "@/components/models/charts";
import type { OutcomeCalibration } from "@/lib/models";
import { cn } from "@/lib/utils";

/** Reliability of one outcome at a time, picked from a row of toggles. */
export function OutcomeCalibrationPicker({
  outcomes,
  calibration,
}: {
  outcomes: { key: string; label: string }[];
  calibration: Record<string, OutcomeCalibration>;
}) {
  const [active, setActive] = useState("four");
  const current = calibration[active];
  return (
    <div className="flex flex-col gap-4">
      <div role="group" aria-label="Outcome" className="flex flex-wrap gap-1.5">
        {outcomes.map((o) => (
          <button
            key={o.key}
            type="button"
            aria-pressed={o.key === active}
            onClick={() => setActive(o.key)}
            className={cn(
              "h-8 rounded-lg border px-3 text-xs transition-colors",
              o.key === active
                ? "border-primary/50 bg-primary/10 text-foreground"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
      <OutcomeCalibrationChart bins={current.bins} />
      <p className="text-xs text-muted-foreground">
        Predicted{" "}
        <span className="font-mono text-foreground tabular-nums">
          {(current.predicted * 100).toFixed(2)}%
        </span>{" "}
        of balls, observed{" "}
        <span className="font-mono text-foreground tabular-nums">
          {(current.observed * 100).toFixed(2)}%
        </span>
        ; calibration error{" "}
        <span className="font-mono text-foreground tabular-nums">
          {(current.ece * 100).toFixed(2)}
        </span>{" "}
        points. Each dot is a tenth of the test balls, grouped by predicted probability.
      </p>
    </div>
  );
}
