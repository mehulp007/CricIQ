"use client";

import { Pause, Play, SkipBack, SkipForward, StepBack, StepForward } from "lucide-react";
import type { Dispatch } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SPEEDS, type ReplayAction, type ReplayState, type Speed } from "@/lib/replay/state";
import { cn } from "@/lib/utils";

export interface OverOption {
  label: string;
  index: number;
}

export function ReplayControls({
  state,
  dispatch,
  overs,
  ballLabel,
  speeds = SPEEDS,
  jumpLabel = "Jump to over",
}: {
  state: ReplayState;
  dispatch: Dispatch<ReplayAction>;
  overs: OverOption[];
  ballLabel: string;
  speeds?: readonly Speed[];
  jumpLabel?: string;
}) {
  const { cursor, total, playing, speed } = state;
  const currentOver = [...overs].reverse().find((o) => o.index <= cursor);

  return (
    <div
      role="toolbar"
      aria-label="Replay controls"
      className="sticky bottom-3 z-20 flex flex-col gap-3 rounded-2xl border border-border bg-popover/90 p-3 shadow-lg backdrop-blur-md sm:flex-row sm:items-center"
    >
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Back to start"
          onClick={() => dispatch({ type: "start" })}
        >
          <SkipBack />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Previous ball"
          onClick={() => dispatch({ type: "prev" })}
        >
          <StepBack />
        </Button>
        <Button
          size="icon-lg"
          className="rounded-full"
          aria-label={playing ? "Pause" : "Play"}
          onClick={() => dispatch({ type: "toggle" })}
        >
          {playing ? <Pause /> : <Play />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Next ball"
          onClick={() => dispatch({ type: "next" })}
        >
          <StepForward />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Jump to end"
          onClick={() => dispatch({ type: "end" })}
        >
          <SkipForward />
        </Button>
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <input
          type="range"
          min={-1}
          max={total - 1}
          value={cursor}
          onChange={(e) => dispatch({ type: "seek", cursor: Number(e.target.value) })}
          aria-label="Replay position"
          aria-valuetext={cursor < 0 ? "Before the first ball" : `Ball ${ballLabel}`}
          className="h-1.5 min-w-0 flex-1 cursor-pointer accent-primary"
        />
        <span className="w-12 shrink-0 text-right font-mono text-xs text-muted-foreground tabular-nums">
          {cursor < 0 ? "0.0" : ballLabel}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <div
          className="flex rounded-lg border border-border p-0.5"
          role="group"
          aria-label="Playback speed"
        >
          {speeds.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={speed === s}
              onClick={() => dispatch({ type: "speed", speed: s })}
              className={cn(
                "rounded-md px-2 py-1 font-mono text-xs transition-colors",
                speed === s
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s}×
            </button>
          ))}
        </div>

        <Select
          value={currentOver ? String(currentOver.index) : undefined}
          onValueChange={(v) => dispatch({ type: "seek", cursor: Number(v) })}
        >
          <SelectTrigger className="w-40" aria-label={jumpLabel}>
            <SelectValue placeholder={jumpLabel} />
          </SelectTrigger>
          <SelectContent className="max-h-80">
            {overs.map((o) => (
              <SelectItem key={o.index} value={String(o.index)}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
