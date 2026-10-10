"use client";

import { Keyboard } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useReducer, useRef } from "react";

import { BallFeed } from "@/components/replay/ball-feed";
import { CreasePanel } from "@/components/replay/crease-panel";
import { ExplainPanel } from "@/components/replay/explain-panel";
import { PressurePanel } from "@/components/replay/pressure-panel";
import { WhatIfPanel } from "@/components/replay/what-if-panel";
import { ProjectionPanel } from "@/components/replay/projection-panel";
import { LiveScorecard } from "@/components/replay/live-scorecard";
import { type OverOption, ReplayControls } from "@/components/replay/replay-controls";
import { Scoreboard } from "@/components/replay/scoreboard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Timeline } from "@/lib/api/types";
import type { CompetitionId } from "@/lib/competitions";
import { inningsLabel } from "@/lib/format";
import { buildFrames, overStarts, scorecardAt } from "@/lib/replay/engine";
import { initialState, intervalFor, replayReducer, type Speed } from "@/lib/replay/state";
import { wpAt } from "@/lib/replay/win-probability";

// The charts load after the replay paints: the charting library stays out of its first JavaScript.
const ReplayCharts = dynamic(
  () => import("@/components/replay/replay-charts").then((m) => m.ReplayCharts),
  { ssr: false, loading: () => <div className="h-80 animate-pulse rounded-xl bg-muted/40" /> },
);

const SPEED_KEYS: Record<string, Speed> = { "1": 1, "2": 2, "4": 4 };

/** `?ball=2.118` (innings.sequence) opens the replay at that delivery. */
function linkedBall(timeline: Timeline): number | null {
  const param = new URLSearchParams(window.location.search).get("ball");
  const match = param?.match(/^(\d+)\.(\d+)$/);
  if (!match) return null;
  const [innings, seq] = [Number(match[1]), Number(match[2])];
  const index = timeline.deliveries.findIndex((d) => d.innings_no === innings && d.seq_no === seq);
  return index >= 0 ? index : null;
}

const INTERACTIVE_ROLES = new Set([
  "button",
  "combobox",
  "listbox",
  "option",
  "slider",
  "tab",
  "menuitem",
]);

/**
 * Global shortcuts yield to focused controls: inputs, buttons, dropdowns and
 * tabs already handle Space and the arrow keys themselves.
 */
function isInteractive(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(target.tagName)) return true;
  const role = target.getAttribute("role");
  return role !== null && INTERACTIVE_ROLES.has(role);
}

export function MatchCenter({
  timeline,
  competition,
  simulator,
}: {
  timeline: Timeline;
  competition: CompetitionId;
  /** Whether a simulator serves this competition (the what-if sandbox needs one). */
  simulator: boolean;
}) {
  const frames = useMemo(() => buildFrames(timeline), [timeline]);
  const [state, dispatch] = useReducer(replayReducer, frames.length, (n) => initialState(n));
  const { cursor, playing, speed } = state;
  const rootRef = useRef<HTMLDivElement>(null);

  // Autoplay: one ball per interval while playing.
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => dispatch({ type: "tick" }), intervalFor(speed));
    return () => window.clearInterval(id);
  }, [playing, speed]);

  // Keyboard: Space play/pause, arrows step, Home/End jump, 1/2/4 speed.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (isInteractive(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      const actions: Record<string, () => void> = {
        " ": () => dispatch({ type: "toggle" }),
        ArrowRight: () => dispatch({ type: "next" }),
        ArrowLeft: () => dispatch({ type: "prev" }),
        Home: () => dispatch({ type: "start" }),
        End: () => dispatch({ type: "end" }),
      };
      const action =
        actions[event.key] ??
        (SPEED_KEYS[event.key]
          ? () => dispatch({ type: "speed", speed: SPEED_KEYS[event.key] })
          : null);
      if (action) {
        event.preventDefault();
        action();
      }
    }
    window.addEventListener("keydown", onKey);
    // Marks the moment shortcuts are live (hydrated); end-to-end tests wait for it.
    rootRef.current?.setAttribute("data-replay-ready", "");
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Deep links from turning points elsewhere in the app. The URL is only
  // readable after hydration, so this syncs once from outside React.
  useEffect(() => {
    const index = linkedBall(timeline);
    if (index !== null) dispatch({ type: "seek", cursor: index });
  }, [timeline]);

  const overs: OverOption[] = useMemo(() => {
    const innings = new Map(timeline.innings.map((i) => [i.innings_no, i]));
    return overStarts(timeline).map((o) => {
      const inn = innings.get(o.inningsNo)!;
      const team = timeline.teams[inn.batting_team_id].franchise_id;
      return {
        index: o.index,
        label: inn.is_super_over
          ? `${inningsLabel(o.inningsNo, true)} · ${team}`
          : `${team} · over ${o.over}`,
      };
    });
  }, [timeline]);

  const frame = cursor >= 0 ? frames[cursor] : null;
  const atEnd = cursor === frames.length - 1;
  const cards = useMemo(() => scorecardAt(timeline, cursor), [timeline, cursor]);
  const wp = wpAt(timeline, cursor);
  const seek = (index: number) => dispatch({ type: "seek", cursor: index });

  return (
    <div ref={rootRef} className="flex flex-col gap-4">
      <Tabs defaultValue="live">
        <div className="flex items-center justify-between gap-3">
          <TabsList>
            <TabsTrigger value="live">Live view</TabsTrigger>
            <TabsTrigger value="scorecard">Scorecard</TabsTrigger>
          </TabsList>
          <p className="hidden items-center gap-1.5 text-xs text-muted-foreground md:flex">
            <Keyboard className="size-3.5" aria-hidden="true" />
            Space play · ← → step · 1 2 4 speed
          </p>
        </div>

        <TabsContent value="live" className="mt-4">
          <div className="grid gap-4 lg:grid-cols-12">
            <div className="flex flex-col gap-4 lg:col-span-7">
              <Scoreboard timeline={timeline} frame={frame} atEnd={atEnd} wp={wp} />
              <ProjectionPanel timeline={timeline} cursor={cursor} />
              {frame && <CreasePanel timeline={timeline} frame={frame} />}
              <ReplayCharts timeline={timeline} cursor={cursor} onSeek={seek} />
            </div>
            <div className="flex flex-col gap-4 lg:col-span-5">
              <PressurePanel timeline={timeline} cursor={cursor} competition={competition} />
              {simulator && (
                <WhatIfPanel timeline={timeline} cursor={cursor} competition={competition} />
              )}
              <ExplainPanel timeline={timeline} cursor={cursor} />
              <BallFeed timeline={timeline} frames={frames} cursor={cursor} />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="scorecard" className="mt-4">
          <LiveScorecard timeline={timeline} cards={cards} competition={competition} />
        </TabsContent>
      </Tabs>

      <ReplayControls
        state={state}
        dispatch={dispatch}
        overs={overs}
        ballLabel={frame?.delivery.ball_label ?? "0.0"}
      />
    </div>
  );
}
