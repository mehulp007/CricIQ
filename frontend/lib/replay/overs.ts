/**
 * The over-by-over view of a limited-overs replay: each over of the two main innings as a bar,
 * as it stood at the cursor ball (super overs are left out).
 */
import type { Timeline } from "@/lib/api/types";

export interface OverBar {
  /** 1 (batting first) or 2 (chasing). */
  inningsNo: 1 | 2;
  /** 1-based. */
  over: number;
  /** Runs off the over so far. */
  runs: number;
  /** Dismissals in the over so far, in order. */
  wickets: number;
  /** The index of the over's first delivery (where clicking the over seeks to). */
  startIndex: number;
  /** The over the cursor ball belongs to. */
  current: boolean;
  /** Every ball of the over has been bowled by the cursor. */
  complete: boolean;
}

/** Every over begun by the cursor ball, innings 1 then 2. */
export function overBars(timeline: Timeline, cursor: number): OverBar[] {
  const bars = new Map<string, OverBar>();
  const last = new Map<string, number>();
  timeline.deliveries.forEach((d, i) => {
    if (d.innings_no !== 1 && d.innings_no !== 2) return;
    last.set(`${d.innings_no}-${d.over_no}`, i);
    if (i > cursor) return;
    const key = `${d.innings_no}-${d.over_no}`;
    const bar = bars.get(key) ?? {
      inningsNo: d.innings_no as 1 | 2,
      over: d.over_no + 1,
      runs: 0,
      wickets: 0,
      startIndex: i,
      current: false,
      complete: false,
    };
    bar.runs += d.runs_total;
    if (d.wicket?.is_dismissal) bar.wickets += 1;
    bars.set(key, bar);
  });
  const current = cursor >= 0 ? timeline.deliveries[cursor] : undefined;
  for (const [key, bar] of bars) {
    bar.complete = (last.get(key) ?? Infinity) <= cursor;
    bar.current = current !== undefined && key === `${current.innings_no}-${current.over_no}`;
  }
  return [...bars.values()].sort((x, y) => x.inningsNo - y.inningsNo || x.over - y.over);
}

/** One sentence about an over, for the caption under the view. */
export function describeOver(bar: OverBar, team: string): string {
  const runs = `${bar.runs} run${bar.runs === 1 ? "" : "s"}`;
  const wickets = bar.wickets > 0 ? `, ${bar.wickets} wicket${bar.wickets === 1 ? "" : "s"}` : "";
  return `${team}, over ${bar.over}: ${runs}${wickets}${bar.complete ? "" : " so far"}`;
}
