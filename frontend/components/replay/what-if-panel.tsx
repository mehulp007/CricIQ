"use client";

import { Dices, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { StateResult, Timeline } from "@/lib/api/types";
import {
  WHATIF_SIMULATIONS,
  type WhatIfPosition,
  oversText,
  pct,
  pointsText,
  whatIfPosition,
} from "@/lib/simulator";
import { cn } from "@/lib/utils";

interface Score {
  runs: number;
  wickets: number;
  balls: number;
}

function scoreAt(timeline: Timeline, cursor: number, position: WhatIfPosition): Score {
  if (position.seqNo === 0 || cursor < 0) return { runs: 0, wickets: 0, balls: 0 };
  const d = timeline.deliveries[cursor];
  return { runs: d.team_runs, wickets: d.team_wickets, balls: d.legal_ball_no };
}

function Stepper({
  label,
  value,
  steps,
  allowed,
  onChange,
}: {
  label: string;
  value: string;
  steps: number[];
  allowed: (step: number) => boolean;
  onChange: (delta: number) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      <div className="flex flex-wrap items-center gap-1" role="group" aria-label={label}>
        {steps.map((step) => (
          <button
            key={step}
            type="button"
            disabled={!allowed(step)}
            onClick={() => onChange(step)}
            className="h-7 min-w-9 rounded-md border border-border px-2 font-mono text-xs text-muted-foreground tabular-nums transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
            aria-label={`${step > 0 ? "Add" : "Remove"} ${Math.abs(step)} ${label.toLowerCase()}`}
          >
            {step > 0 ? `+${step}` : `−${-step}`}
          </button>
        ))}
        <span className="ml-1 font-mono text-sm font-semibold tabular-nums">{value}</span>
      </div>
    </div>
  );
}

/**
 * What if the score were different at this ball? The rest of the match is
 * simulated from the real and the edited score, and the difference moves the
 * win probability model's estimate.
 */
export function WhatIfPanel({ timeline, cursor }: { timeline: Timeline; cursor: number }) {
  const position = whatIfPosition(timeline, cursor);
  const key = position ? `${position.inningsNo}:${position.seqNo}` : "none";
  return <WhatIf key={key} timeline={timeline} cursor={cursor} position={position} />;
}

function WhatIf({
  timeline,
  cursor,
  position,
}: {
  timeline: Timeline;
  cursor: number;
  position: WhatIfPosition | null;
}) {
  const [runs, setRuns] = useState(0);
  const [wickets, setWickets] = useState(0);
  const [result, setResult] = useState<StateResult | null>(null);
  const [status, setStatus] = useState<"idle" | "running" | "error">("idle");

  if (!position) {
    return (
      <section
        aria-label="What if?"
        className="rounded-2xl border border-border bg-card/70 p-5 text-sm text-muted-foreground"
      >
        <h2 className="mb-1 text-xs tracking-wide text-muted-foreground uppercase">What if?</h2>
        The match is over at this ball. Step back to try a different score.
      </section>
    );
  }
  const real = scoreAt(timeline, cursor, position);
  const innings = timeline.innings.find((i) => i.innings_no === position.inningsNo);
  const batting = innings ? timeline.teams[innings.batting_team_id] : null;
  const edited = { runs: Math.max(0, real.runs + runs), wickets: real.wickets + wickets };
  const changed = runs !== 0 || wickets !== 0;

  async function simulate() {
    if (!position) return;
    setStatus("running");
    try {
      const response = await fetch("/api/simulate/state", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          match_id: timeline.summary.match_id,
          innings_no: position.inningsNo,
          seq_no: position.seqNo,
          runs: edited.runs,
          wickets: edited.wickets,
          simulations: WHATIF_SIMULATIONS,
        }),
      });
      if (!response.ok) throw new Error(String(response.status));
      setResult((await response.json()) as StateResult);
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  const base = result?.model_win_pct ?? result?.actual.simulated_win_pct ?? null;
  return (
    <section
      aria-label="What if?"
      className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs tracking-wide text-muted-foreground uppercase">What if?</h2>
        <span className="rounded-md border border-border px-2 py-0.5 text-[10px] tracking-wide text-muted-foreground uppercase">
          Model simulation
        </span>
      </div>
      <p className="text-sm">
        {batting?.franchise_id ?? "Batting side"}{" "}
        <span className="font-mono tabular-nums">
          {real.runs}/{real.wickets}
        </span>{" "}
        after {oversText(real.balls)} overs. Change the score, then play the rest of the match{" "}
        {WHATIF_SIMULATIONS.toLocaleString("en-IN")} times.
      </p>
      <div className="flex flex-wrap gap-x-6 gap-y-3">
        <Stepper
          label="Runs"
          value={`${edited.runs}`}
          steps={[-10, -5, 5, 10]}
          allowed={(d) => real.runs + runs + d >= 0 && real.runs + runs + d <= 400}
          onChange={(d) => {
            setRuns((r) => r + d);
            setResult(null);
          }}
        />
        <Stepper
          label="Wickets"
          value={`${edited.wickets}`}
          steps={[-1, 1]}
          allowed={(d) => wickets + d >= 0 && real.wickets + wickets + d <= 9}
          onChange={(d) => {
            setWickets((w) => w + d);
            setResult(null);
          }}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={simulate}
          disabled={status === "running"}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          <Dices className="size-3.5" aria-hidden="true" />
          {status === "running"
            ? "Simulating…"
            : changed
              ? "Simulate the what-if"
              : "Simulate from here"}
        </button>
        {changed && (
          <button
            type="button"
            onClick={() => {
              setRuns(0);
              setWickets(0);
              setResult(null);
            }}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-3 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <RotateCcw className="size-3.5" aria-hidden="true" />
            Real score
          </button>
        )}
      </div>
      <div aria-live="polite" className="flex flex-col gap-2">
        {status === "error" && (
          <p className="text-xs text-negative">
            The simulator is waking up. Try again in a moment.
          </p>
        )}
        {result && base !== null && (
          <>
            <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-mono text-2xl font-semibold tabular-nums">
                {pct(result.whatif_win_pct)}
              </span>
              <span className="text-sm text-muted-foreground">
                {result.batting.franchise_id} win chance
                {changed ? `, from ${pct(base)}` : ""}
              </span>
              {changed && (
                <span
                  className={cn(
                    "font-mono text-sm tabular-nums",
                    result.whatif_win_pct >= base ? "text-positive" : "text-negative",
                  )}
                >
                  {pointsText(result.whatif_win_pct - base)}
                </span>
              )}
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {result.innings_no === 1 ? "Projected total" : "Chase ends on"}: median{" "}
              <span className="font-mono text-foreground">{result.edited.total.p50}</span>, 80%
              between {result.edited.total.p10} and {result.edited.total.p90}
              {result.target ? ` (target ${result.target})` : ""}.{" "}
              {result.model_win_pct !== null && result.model_win_pct !== undefined
                ? "The win probability model's estimate at the real score, moved by how much the simulations change."
                : "Simulated chance."}{" "}
              <Link
                href="/models?tab=simulator#simulator"
                className="text-foreground underline-offset-4 hover:underline"
              >
                How
              </Link>
            </p>
          </>
        )}
      </div>
    </section>
  );
}
