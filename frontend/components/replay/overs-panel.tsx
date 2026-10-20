"use client";

import { Box, ChartColumn } from "lucide-react";
import dynamic from "next/dynamic";
import { useMemo, useRef, useState, useSyncExternalStore } from "react";

import { Legend, sidesOf } from "@/components/replay/chart-parts";
import { ManhattanChart } from "@/components/replay/manhattan-chart";
import type { OversPalette } from "@/components/three/scenes/overs-scene";
import { SceneBoundary, use3DAllowed, useInView, usePageVisible } from "@/components/three/use-3d";
import { useResolvedTheme } from "@/components/theme/use-resolved-theme";
import type { Timeline } from "@/lib/api/types";
import { tokenColor } from "@/lib/css-color";
import { describeOver, overBars, type OverBar } from "@/lib/replay/overs";
import { pressureAt, pressureBand } from "@/lib/replay/pressure";
import { inningsOvers } from "@/lib/replay/win-probability";
import { cn } from "@/lib/utils";

// three.js loads only when the 3D view is on screen and allowed.
const OversScene = dynamic(() => import("@/components/three/scenes/overs-scene"), { ssr: false });

/** The 3D view needs a laptop-sized screen: its overs are small targets. */
const MIN_WIDTH = 1024;
const VIEW_KEY = "criciq-overs-view";
type View = "3d" | "2d";

// The visitor's choice of view, remembered in this browser.
const viewListeners = new Set<() => void>();
function readView(): View {
  try {
    return window.localStorage.getItem(VIEW_KEY) === "2d" ? "2d" : "3d";
  } catch {
    return "3d";
  }
}
function storeView(view: View) {
  try {
    window.localStorage.setItem(VIEW_KEY, view);
  } catch {
    // Private windows may refuse: the choice lasts for this page only.
  }
  viewListeners.forEach((listener) => listener());
}
function subscribeView(listener: () => void) {
  viewListeners.add(listener);
  return () => viewListeners.delete(listener);
}

const TURF: Record<"dark" | "light", [string, string]> = {
  dark: ["#1f4a2a", "#245532"],
  light: ["#4f9a4a", "#58a552"],
};

function ViewSwitch({ view, onChange }: { view: View; onChange: (view: View) => void }) {
  const options: { value: View; label: string; icon: typeof Box }[] = [
    { value: "3d", label: "3D", icon: Box },
    { value: "2d", label: "Chart", icon: ChartColumn },
  ];
  return (
    <div role="group" aria-label="View" className="flex rounded-lg border border-border p-0.5">
      {options.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          aria-pressed={view === value}
          onClick={() => onChange(value)}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
            view === value
              ? "bg-secondary text-secondary-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon className="size-3.5" aria-hidden="true" />
          {label}
        </button>
      ))}
    </div>
  );
}

/**
 * Over by over: the runs in each over of both innings, in 3D (bars rising on a strip of turf,
 * stumps falling on wickets, floodlights following the pressure) or as the Manhattan chart. The
 * chart shows first, and always on phones, with reduced motion or without WebGL.
 */
export function OversPanel({
  timeline,
  cursor,
  onSeek,
}: {
  timeline: Timeline;
  cursor: number;
  onSeek: (index: number) => void;
}) {
  const stage = useRef<HTMLDivElement>(null);
  const theme = useResolvedTheme();
  const view = useSyncExternalStore(subscribeView, readView, () => "3d" as View);
  // The 3D view (and the switch to it) appears once 3D may start: after the visitor's first move,
  // on a capable laptop-sized screen. Until then, and otherwise, the chart shows.
  const allowed = use3DAllowed(MIN_WIDTH);
  const inView = useInView(stage);
  const pageVisible = usePageVisible();
  const [ready, setReady] = useState(false);
  const [settled, setSettled] = useState(false);
  const [hovered, setHovered] = useState<OverBar | null>(null);

  const sides = sidesOf(timeline);
  const overs = inningsOvers(timeline);
  const bars = useMemo(() => overBars(timeline, cursor), [timeline, cursor]);
  const pressure = pressureAt(timeline, cursor);
  const palette: OversPalette = useMemo(
    () => ({
      a: tokenColor("--team-a"),
      b: tokenColor("--team-b"),
      turf: TURF[theme][0],
      turfStripe: TURF[theme][1],
      chalk: "#f4f4f0",
    }),
    [theme],
  );

  const show3D = allowed && view === "3d";
  const mounted = show3D && (inView || ready);
  // The chart stays under the 3D view until it has faded in, then leaves.
  const chartShown = !(show3D && ready && settled);

  const caption = hovered
    ? `${describeOver(hovered, sides[hovered.inningsNo - 1].short)}. Click to replay it.`
    : show3D && ready
      ? `Click an over to replay it from its first ball. The floodlights follow the pressure on the next ball${pressure ? ` (${pressureBand(pressure.pressure).toLowerCase()})` : ""}.`
      : null;

  return (
    <section aria-labelledby="overs-heading" className="panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <h2 id="overs-heading" className="text-sm font-semibold">
            Over by over
          </h2>
          <p className="text-xs text-muted-foreground">
            Runs in each over, with the wickets on top.
          </p>
        </div>
        {allowed && (
          <ViewSwitch
            view={view}
            onChange={(next) => {
              setReady(false);
              setSettled(false);
              storeView(next);
            }}
          />
        )}
      </div>

      <div ref={stage} className="relative mt-4 h-72">
        {chartShown && (
          <div
            aria-hidden={show3D && ready ? true : undefined}
            className="absolute inset-0"
            data-testid="overs-chart"
          >
            <ManhattanChart timeline={timeline} cursor={cursor} />
          </div>
        )}
        {mounted && (
          <div
            role="img"
            aria-label={`The runs in each over in 3D: ${sides[0].name} batting first behind, ${sides[1].name} chasing in front. The chart view lists them.`}
            data-testid="overs-3d"
            data-scene-state={ready ? "3d" : "loading"}
            onTransitionEnd={() => setSettled(ready)}
            className={cn(
              "absolute inset-0 rounded-xl bg-card transition-opacity duration-500",
              ready ? "opacity-100" : "pointer-events-none opacity-0",
            )}
          >
            <SceneBoundary>
              <OversScene
                active={inView && pageVisible}
                theme={theme}
                onReady={() => setReady(true)}
                bars={bars}
                overs={overs}
                pressure={pressure?.pressure ?? null}
                palette={palette}
                onSeek={onSeek}
                onHover={setHovered}
              />
            </SceneBoundary>
          </div>
        )}
      </div>

      <div className="mt-3 flex min-h-5 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <Legend sides={sides} />
        {caption && <p className="text-xs text-muted-foreground">{caption}</p>}
      </div>
    </section>
  );
}
