/**
 * Test replays: pure helpers over a Test timeline.
 *
 * A Test has up to four innings and three results. The API stores, after every
 * ball, the chance that the side batting first ("team A") wins (`wp`) and that
 * the match is drawn (`wp_draw`); the other side wins with the rest. Days are
 * estimated (`timeline.days`): Cricsheet has the dates a Test was played on but
 * not when each day's play began.
 */
import type { Timeline, TimelineDelivery } from "@/lib/api/types";

export interface Outcome {
  /** Team A (batted first) wins, the match is drawn, team B wins. */
  a: number;
  draw: number;
  b: number;
}

function triple(wp: number | null | undefined, draw: number | null | undefined): Outcome | null {
  if (wp === null || wp === undefined || draw === null || draw === undefined) return null;
  return { a: wp, draw, b: Math.max(1 - wp - draw, 0) };
}

/** The three chances after the cursor ball (before the first ball at -1). */
export function outcomeAt(timeline: Timeline, cursor: number): Outcome | null {
  if (cursor < 0) {
    const first = timeline.innings[0];
    return first ? triple(first.wp_start, first.draw_start) : null;
  }
  for (let i = Math.min(cursor, timeline.deliveries.length - 1); i >= 0; i--) {
    const d = timeline.deliveries[i];
    const found = triple(d.wp, d.wp_draw);
    if (found) return found;
  }
  return outcomeAt(timeline, -1);
}

/** Legal balls bowled in the match before each innings began, by innings number. */
export function inningsOffsets(timeline: Timeline): Map<number, number> {
  const balls = new Map<number, number>();
  for (const d of timeline.deliveries) balls.set(d.innings_no, d.legal_ball_no);
  const offsets = new Map<number, number>();
  let total = 0;
  for (const inn of timeline.innings) {
    offsets.set(inn.innings_no, total);
    total += balls.get(inn.innings_no) ?? 0;
  }
  return offsets;
}

/** Overs bowled in the match after a delivery (all innings so far). */
export function matchOvers(d: TimelineDelivery, offsets: Map<number, number>): number {
  return ((offsets.get(d.innings_no) ?? 0) + d.legal_ball_no) / 6;
}

export interface OutcomePoint extends Outcome {
  x: number; // overs bowled in the match
  index: number; // -1 for an innings start
  label: string;
}

/** The three chances over the match, up to the cursor, against overs bowled in the match. */
export function outcomeSeries(timeline: Timeline, cursor: number): OutcomePoint[] {
  const offsets = inningsOffsets(timeline);
  const points: OutcomePoint[] = [];
  const inningsStart = new Map(timeline.innings.map((i) => [i.innings_no, i]));
  timeline.deliveries.forEach((d, index) => {
    if (index > cursor) return;
    const prev = timeline.deliveries[index - 1];
    if (!prev || prev.innings_no !== d.innings_no) {
      const inn = inningsStart.get(d.innings_no);
      const start = inn ? triple(inn.wp_start, inn.draw_start) : null;
      if (start) {
        points.push({
          ...start,
          x: (offsets.get(d.innings_no) ?? 0) / 6,
          index: -1,
          label: index === 0 ? "Start" : "Innings break",
        });
      }
    }
    const o = triple(d.wp, d.wp_draw);
    if (o) points.push({ ...o, x: matchOvers(d, offsets), index, label: d.ball_label ?? "" });
  });
  return points;
}

export interface TestTurningPoint {
  index: number;
  /** Change in team A's expected result (a win 1, a draw a half), in points. */
  swing: number;
  side: "a" | "b";
}

/** The balls that moved the expected result most, up to ``upTo``, largest first. The
 * match's last ball (the result itself) is left out. */
export function testTurningPoints(
  timeline: Timeline,
  count = 5,
  upTo = Infinity,
): TestTurningPoint[] {
  const last = timeline.deliveries.length - 1;
  const value = (o: Outcome) => o.a + o.draw / 2;
  const found: TestTurningPoint[] = [];
  let before = outcomeAt(timeline, -1);
  let inningsNo = timeline.deliveries[0]?.innings_no;
  timeline.deliveries.forEach((d, index) => {
    if (d.innings_no !== inningsNo) {
      const inn = timeline.innings.find((i) => i.innings_no === d.innings_no);
      before = inn ? (triple(inn.wp_start, inn.draw_start) ?? before) : before;
      inningsNo = d.innings_no;
    }
    const after = triple(d.wp, d.wp_draw);
    if (after && before && index <= upTo && index < last) {
      const swing = (value(after) - value(before)) * 100;
      found.push({ index, swing, side: swing > 0 ? "a" : "b" });
    }
    if (after) before = after;
  });
  return found.sort((x, y) => Math.abs(y.swing) - Math.abs(x.swing)).slice(0, count);
}

export interface SideTotals {
  /** Runs of team A (batted first) and team B, over every innings up to the cursor. */
  a: number;
  b: number;
}

/** Each side's runs in the match so far, after the cursor ball. */
export function totalsAt(timeline: Timeline, cursor: number): SideTotals {
  const teamA = timeline.summary.team_a.team_season_id;
  const batting = new Map(timeline.innings.map((i) => [i.innings_no, i.batting_team_id]));
  const last = new Map<number, number>();
  for (let i = 0; i <= cursor && i < timeline.deliveries.length; i++) {
    const d = timeline.deliveries[i];
    last.set(d.innings_no, d.team_runs);
  }
  const totals = { a: 0, b: 0 };
  for (const [innings, runs] of last) {
    if (batting.get(innings) === teamA) totals.a += runs;
    else totals.b += runs;
  }
  return totals;
}

/** Where the match stands for the side batting at the cursor: "lead by 120", "trail by 45",
 * "need 210 to win", "scores level". */
export function situation(timeline: Timeline, cursor: number): string | null {
  if (cursor < 0) return null;
  const d = timeline.deliveries[cursor];
  const inn = timeline.innings.find((i) => i.innings_no === d.innings_no);
  if (!inn) return null;
  const totals = totalsAt(timeline, cursor);
  const battingIsA = inn.batting_team_id === timeline.summary.team_a.team_season_id;
  const own = battingIsA ? totals.a : totals.b;
  const other = battingIsA ? totals.b : totals.a;
  const name = timeline.teams[inn.batting_team_id]?.name ?? "";
  if (d.innings_no === 1) return null;
  if (d.innings_no === 4) {
    const needed = other - own + 1;
    if (needed <= 0) return `${name} have won`;
    return `${name} need ${needed} to win`;
  }
  if (own === other) return "Scores level";
  return own > other ? `${name} lead by ${own - other}` : `${name} trail by ${other - own}`;
}

/** The delivery index each estimated day begins at (day 1 at -1, before the first ball). */
export function dayStarts(timeline: Timeline): { day: number; index: number }[] {
  if (!timeline.days) return [];
  const position = new Map(timeline.deliveries.map((d, i) => [`${d.innings_no}.${d.seq_no}`, i]));
  return timeline.days.map((m) => ({
    day: m.day,
    index: m.day === 1 ? -1 : (position.get(`${m.innings_no}.${m.seq_no}`) ?? -1),
  }));
}

/** The estimated day of play at the cursor (1 before the first ball). */
export function dayAt(timeline: Timeline, cursor: number): number | null {
  const starts = dayStarts(timeline);
  if (starts.length === 0) return null;
  let day = 1;
  for (const s of starts) if (s.index <= cursor) day = s.day;
  return day;
}

export interface Jump {
  label: string;
  index: number;
}

/** Places to jump to: each day, each innings and every ten overs of an innings (one entry
 * per ball, naming everything that starts there). */
export function testJumps(timeline: Timeline): Jump[] {
  const labels = new Map<number, string[]>();
  const add = (index: number, label: string) =>
    labels.set(index, [...(labels.get(index) ?? []), label]);
  const days = new Map(dayStarts(timeline).map((s) => [Math.max(s.index, 0), s.day]));
  const batting = new Map(timeline.innings.map((i) => [i.innings_no, i.batting_team_id]));
  timeline.deliveries.forEach((d, index) => {
    const prev = timeline.deliveries[index - 1];
    const team = timeline.teams[batting.get(d.innings_no) ?? ""]?.franchise_id ?? "";
    const day = days.get(index);
    if (day !== undefined) add(index, `Day ${day} (est.)`);
    if (!prev || prev.innings_no !== d.innings_no) {
      add(index, `Innings ${d.innings_no} · ${team}`);
    } else if (prev.over_no !== d.over_no && d.over_no % 10 === 0) {
      add(index, `${team} · over ${d.over_no + 1}`);
    }
  });
  return [...labels].map(([index, parts]) => ({ index, label: parts.join(" · ") }));
}
