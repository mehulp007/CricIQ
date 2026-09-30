/**
 * Win probability in the replay: pure helpers over a timeline.
 *
 * The API stores the win probability of the side batting first ("team A")
 * after every ball, plus an explanation for the side batting at that moment.
 * Everything here is derived from those two numbers, so the UI never needs a
 * model of its own.
 */
import { oversNotation } from "@/lib/cricket";
import type { Timeline, TimelineDelivery, TimelineInnings } from "@/lib/api/types";

export type Side = "a" | "b";

/** Team A's win probability after the cursor ball (before the first ball at -1). */
export function wpAt(timeline: Timeline, cursor: number): number | null {
  if (cursor < 0) return timeline.innings[0]?.wp_start ?? null;
  const d = timeline.deliveries[cursor];
  if (!d) return null;
  if (d.wp !== null && d.wp !== undefined) return d.wp;
  return lastKnownWp(timeline, cursor);
}

/** Super overs are not modelled: hold the last regulation estimate. */
function lastKnownWp(timeline: Timeline, cursor: number): number | null {
  for (let i = cursor; i >= 0; i--) {
    const wp = timeline.deliveries[i].wp;
    if (wp !== null && wp !== undefined) return wp;
  }
  return timeline.innings[0]?.wp_start ?? null;
}

function inningsOf(timeline: Timeline, inningsNo: number): TimelineInnings | undefined {
  return timeline.innings.find((i) => i.innings_no === inningsNo);
}

/** Team A's win probability just before delivery ``index``. */
export function wpBefore(timeline: Timeline, index: number): number | null {
  const d = timeline.deliveries[index];
  const prev = timeline.deliveries[index - 1];
  if (prev && prev.innings_no === d.innings_no) return prev.wp ?? null;
  return inningsOf(timeline, d.innings_no)?.wp_start ?? null;
}

/** Change in team A's win probability caused by delivery ``index`` (null if not modelled). */
export function swingAt(timeline: Timeline, index: number): number | null {
  const after = timeline.deliveries[index]?.wp;
  const before = wpBefore(timeline, index);
  if (after === null || after === undefined || before === null) return null;
  return after - before;
}

/** Match overs on a single axis: the chase starts at 20. */
export function matchOvers(d: Pick<TimelineDelivery, "innings_no" | "legal_ball_no">): number {
  return (d.innings_no - 1) * 20 + d.legal_ball_no / 6;
}

export interface WpPoint {
  x: number;
  wp: number; // team A, percent
  index: number; // -1 for an innings start
  label: string;
}

/** Team A's win probability over the match, up to the cursor. */
export function wpSeries(timeline: Timeline, cursor: number): WpPoint[] {
  const points: WpPoint[] = [];
  const first = timeline.innings[0];
  if (first?.wp_start !== null && first?.wp_start !== undefined) {
    points.push({ x: 0, wp: first.wp_start * 100, index: -1, label: "Start" });
  }
  timeline.deliveries.forEach((d, index) => {
    if (index > cursor || d.wp === null || d.wp === undefined) return;
    const prev = timeline.deliveries[index - 1];
    if (prev && prev.innings_no !== d.innings_no) {
      const start = inningsOf(timeline, d.innings_no)?.wp_start;
      if (start !== null && start !== undefined) {
        points.push({
          x: (d.innings_no - 1) * 20,
          wp: start * 100,
          index: -1,
          label: "Innings break",
        });
      }
    }
    points.push({ x: matchOvers(d), wp: d.wp * 100, index, label: d.ball_label ?? "" });
  });
  return points;
}

export interface TurningPoint {
  index: number;
  swing: number; // points, positive = team A gained
  side: Side;
}

/** The biggest swings of the match up to ``upTo`` (default: all), largest first. */
export function turningPoints(timeline: Timeline, count = 5, upTo = Infinity): TurningPoint[] {
  const swings: TurningPoint[] = [];
  timeline.deliveries.forEach((_, index) => {
    if (index > upTo) return;
    const swing = swingAt(timeline, index);
    if (swing !== null && Math.abs(swing) >= 0.005) {
      swings.push({ index, swing: swing * 100, side: swing > 0 ? "a" : "b" });
    }
  });
  return swings.sort((x, y) => Math.abs(y.swing) - Math.abs(x.swing)).slice(0, count);
}

// --------------------------------------------------------------------------- explanations

export interface Factor {
  key: string;
  points: number; // for the batting side
}

export interface Explanation {
  battingSide: Side;
  inningsNo: number;
  base: number; // the model's average estimate for this innings, 0-1
  factors: Factor[]; // largest first
}

/** Why the model says what it says at the cursor (null once the result is certain). */
export function explanationAt(timeline: Timeline, cursor: number): Explanation | null {
  const model = timeline.win_probability;
  if (!model) return null;
  let values: number[] | null | undefined;
  let inningsNo: number;
  if (cursor < 0) {
    values = timeline.innings[0]?.factors_start;
    inningsNo = 1;
  } else {
    const d = timeline.deliveries[cursor];
    values = d.factors;
    inningsNo = d.innings_no;
  }
  if (!values || inningsNo > 2) return null;
  const points = values;
  return {
    battingSide: inningsNo === 1 ? "a" : "b",
    inningsNo,
    base: inningsNo === 1 ? model.base_innings1 : model.base_innings2,
    factors: model.factor_keys
      .map((key, i) => ({ key, points: points[i] }))
      .sort((x, y) => Math.abs(y.points) - Math.abs(x.points)),
  };
}

/** Runs and wickets in the last 12 legal balls of the innings, up to the cursor. */
export function recentForm(timeline: Timeline, cursor: number): { runs: number; wickets: number } {
  const current = timeline.deliveries[cursor];
  if (!current) return { runs: 0, wickets: 0 };
  let runs = 0;
  let wickets = 0;
  for (let i = cursor; i >= 0; i--) {
    const d = timeline.deliveries[i];
    if (d.innings_no !== current.innings_no || d.legal_ball_no <= current.legal_ball_no - 12) break;
    runs += d.runs_total;
    if (d.wicket?.is_dismissal) wickets += 1;
  }
  return { runs, wickets };
}

export interface FactorText {
  label: string;
  detail: string;
}

/** Plain-language description of a factor at the cursor. */
export function describeFactor(timeline: Timeline, cursor: number, key: string): FactorText {
  const d = cursor >= 0 ? timeline.deliveries[cursor] : null;
  const inningsNo = d?.innings_no ?? 1;
  const innings = inningsOf(timeline, inningsNo);
  const runs = d?.team_runs ?? 0;
  const wickets = d?.team_wickets ?? 0;
  const legal = d?.legal_ball_no ?? 0;
  switch (key) {
    case "situation": {
      if (inningsNo === 1) {
        return {
          label: "Score for the stage",
          detail: legal
            ? `${runs}/${wickets} after ${oversNotation(legal)} overs`
            : "Before the first ball",
        };
      }
      const target = innings?.target_runs ?? 0;
      const need = Math.max(target - runs, 0);
      const left = Math.max((innings?.max_balls ?? 120) - legal, 0);
      return {
        label: "Chase equation",
        detail: `Need ${need} from ${left} ball${left === 1 ? "" : "s"}`,
      };
    }
    case "wickets": {
      const left = 10 - wickets;
      return { label: "Wickets in hand", detail: `${left} wicket${left === 1 ? "" : "s"} left` };
    }
    case "recent": {
      const form = recentForm(timeline, cursor);
      return {
        label: "Last two overs",
        detail: legal
          ? `${form.runs} run${form.runs === 1 ? "" : "s"}, ${form.wickets} wicket${form.wickets === 1 ? "" : "s"}`
          : "No balls bowled yet",
      };
    }
    default:
      return { label: key, detail: "" };
  }
}

/** "62%" with sensible rounding at the extremes ("<1%", ">99%"). */
export function formatPercent(p: number): string {
  const pct = p * 100;
  if (pct > 0 && pct < 1) return "<1%";
  if (pct < 100 && pct > 99) return ">99%";
  return `${Math.round(pct)}%`;
}
