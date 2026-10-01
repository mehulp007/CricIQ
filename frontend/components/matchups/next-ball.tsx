"use client";

import { useState } from "react";

import type { NextBall } from "@/lib/api/types";
import { READINGS, percent } from "@/lib/matchups";
import { cn } from "@/lib/utils";

/** Next-ball outcome odds by phase: from overall records, and adjusted by head-to-head. */
export function NextBallPanel({
  balls,
  hasHistory,
  context,
}: {
  balls: NextBall[];
  hasHistory: boolean;
  context: string;
}) {
  const [phase, setPhase] = useState(balls[1]?.phase ?? balls[0]?.phase);
  const current = balls.find((b) => b.phase === phase) ?? balls[0];
  if (!current) return null;
  const max = Math.max(
    ...current.model.map((o) => o.probability),
    ...current.with_history.map((o) => o.probability),
  );
  const primary = hasHistory ? current.with_history : current.model;
  return (
    <div className="flex flex-col gap-4">
      <div role="group" aria-label="Phase" className="flex flex-wrap gap-1.5">
        {balls.map((b) => (
          <button
            key={b.phase}
            type="button"
            aria-pressed={b.phase === current.phase}
            onClick={() => setPhase(b.phase)}
            className={cn(
              "h-8 rounded-lg border px-3 text-xs transition-colors",
              b.phase === current.phase
                ? "border-primary/50 bg-primary/10 text-foreground"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {b.label}
          </button>
        ))}
      </div>

      <ul
        className="flex flex-col gap-2.5"
        aria-label={`Next ball, ${current.label.toLowerCase()}`}
      >
        {primary.map((o, i) => {
          const model = current.model[i].probability;
          return (
            <li
              key={o.outcome}
              className="grid grid-cols-[5rem_minmax(0,1fr)_7.5rem] items-center gap-3"
            >
              <span className="text-sm">{o.label}</span>
              <span className="relative h-2.5 rounded-full bg-muted" aria-hidden="true">
                <span
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{
                    width: `${(o.probability / max) * 100}%`,
                    background: hasHistory ? READINGS.estimate.color : READINGS.expected.color,
                  }}
                />
                {hasHistory && (
                  <span
                    className="absolute -inset-y-1 w-0.5 rounded-full bg-foreground/70"
                    style={{ left: `calc(${(model / max) * 100}% - 1px)` }}
                  />
                )}
              </span>
              <span className="text-right font-mono text-xs tabular-nums">
                {percent(o.probability)}
                {hasHistory && <span className="text-muted-foreground"> ({percent(model)})</span>}
              </span>
            </li>
          );
        })}
      </ul>

      <p className="text-xs leading-relaxed text-muted-foreground">
        Expected runs per ball{" "}
        <span className="font-mono text-foreground tabular-nums">
          {(hasHistory ? current.expected_runs_with_history : current.expected_runs).toFixed(2)}
        </span>
        {hasHistory && (
          <>
            {" "}
            (overall records alone:{" "}
            <span className="font-mono tabular-nums">{current.expected_runs.toFixed(2)}</span>).
            Bars include the head-to-head record; the tick and the bracketed figure leave it out.
          </>
        )}{" "}
        Assumes: {context.charAt(0).toLowerCase() + context.slice(1)} Model estimate.
      </p>
    </div>
  );
}
