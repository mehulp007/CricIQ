"use client";

import { Keyboard } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useReducer, useRef } from "react";

import { BallFeed } from "@/components/replay/ball-feed";
import { CreasePanel } from "@/components/replay/crease-panel";
import { LiveScorecard } from "@/components/replay/live-scorecard";
import { ProjectionPanel } from "@/components/replay/projection-panel";
import { type OverOption, ReplayControls } from "@/components/replay/replay-controls";
import { ChasePanel } from "@/components/replay/test/chase-panel";
import { TestScoreboard } from "@/components/replay/test/test-scoreboard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Timeline } from "@/lib/api/types";
import type { CompetitionId } from "@/lib/competitions";
import { buildFrames, scorecardAt } from "@/lib/replay/engine";
import { initialState, intervalFor, replayReducer, type Speed } from "@/lib/replay/state";
import { outcomeAt, testJumps } from "@/lib/replay/test";

// The charts load after the replay paints: the charting library stays out of its first JavaScript.
const OutcomeChart = dynamic(
  () => import("@/components/replay/test/outcome-chart").then((m) => m.OutcomeChart),
  { ssr: false, loading: () => <div className="h-72 animate-pulse rounded-xl bg-muted/40" /> },
);
const InningsOvers = dynamic(
  () => import("@/components/replay/test/innings-overs").then((m) => m.InningsOvers),
  { ssr: false, loading: () => <div className="h-56 animate-pulse rounded-xl bg-muted/40" /> },
);

// A Test is about 2,000 balls: faster speeds than a T20's.
const TEST_SPEEDS: readonly Speed[] = [1, 4, 16, 64];
const SPEED_KEYS: Record<string, Speed> = { "1": 1, "2": 4, "3": 16, "4": 64 };

const INTERACTIVE_ROLES = new Set([
  "button",
  "combobox",
  "listbox",
  "option",
  "slider",
  "tab",
  "menuitem",
]);

function isInteractive(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(target.tagName)) return true;
  const role = target.getAttribute("role");
  return role !== null && INTERACTIVE_ROLES.has(role);
}

/** `?ball=2.118` (innings.sequence) opens the replay at that delivery. */
function linkedBall(timeline: Timeline): number | null {
  const param = new URLSearchParams(window.location.search).get("ball");
  const match = param?.match(/^(\d+)\.(\d+)$/);
  if (!match) return null;
  const [innings, seq] = [Number(match[1]), Number(match[2])];
  const index = timeline.deliveries.findIndex((d) => d.innings_no === innings && d.seq_no === seq);
  return index >= 0 ? index : null;
}

/** The replay of a Test: four innings, three results, estimated days, the chase what-if. */
export function TestMatchCenter({
  timeline,
  competition,
}: {
  timeline: Timeline;
  competition: CompetitionId;
}) {
  const frames = useMemo(() => buildFrames(timeline), [timeline]);
  const [state, dispatch] = useReducer(replayReducer, frames.length, (n) => initialState(n));
  const { cursor, playing, speed } = state;
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => dispatch({ type: "tick" }), intervalFor(speed));
    return () => window.clearInterval(id);
  }, [playing, speed]);

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
    rootRef.current?.setAttribute("data-replay-ready", "");
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const index = linkedBall(timeline);
    if (index !== null) dispatch({ type: "seek", cursor: index });
  }, [timeline]);

  const jumps: OverOption[] = useMemo(() => testJumps(timeline), [timeline]);
  const frame = cursor >= 0 ? frames[cursor] : null;
  const atEnd = cursor === frames.length - 1;
  const cards = useMemo(() => scorecardAt(timeline, cursor), [timeline, cursor]);
  const outcome = outcomeAt(timeline, cursor);
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
            Space play · ← → step · 1 2 3 4 speed
          </p>
        </div>

        <TabsContent value="live" className="mt-4">
          <div className="grid gap-4 lg:grid-cols-12">
            <div className="flex flex-col gap-4 lg:col-span-7">
              <TestScoreboard
                timeline={timeline}
                frame={frame}
                cursor={cursor}
                atEnd={atEnd}
                outcome={outcome}
              />
              <ProjectionPanel timeline={timeline} cursor={cursor} />
              {frame && <CreasePanel timeline={timeline} frame={frame} />}
              <section
                aria-label="Charts"
                className="rounded-2xl border border-border bg-card/70 p-5"
              >
                <Tabs defaultValue="chances">
                  <TabsList>
                    <TabsTrigger value="chances">Result chances</TabsTrigger>
                    <TabsTrigger value="overs">Runs per over</TabsTrigger>
                  </TabsList>
                  <TabsContent value="chances" className="mt-4">
                    <OutcomeChart timeline={timeline} cursor={cursor} onSeek={seek} />
                  </TabsContent>
                  <TabsContent value="overs" className="mt-4">
                    <InningsOvers timeline={timeline} cursor={cursor} />
                  </TabsContent>
                </Tabs>
              </section>
            </div>
            <div className="flex flex-col gap-4 lg:col-span-5">
              <ChasePanel timeline={timeline} cursor={cursor} competition={competition} />
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
        overs={jumps}
        ballLabel={frame ? `${frame.delivery.innings_no}·${frame.delivery.ball_label}` : "0.0"}
        speeds={TEST_SPEEDS}
        jumpLabel="Jump to day or innings"
      />
    </div>
  );
}
