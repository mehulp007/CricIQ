/**
 * Replay engine: derives everything the Match Center shows from a timeline.
 *
 * Pure functions only (no React), so it is unit-tested against real matches.
 * A "cursor" is an index into `timeline.deliveries`; -1 means "before the
 * first ball". Every derived value describes the state *after* the cursor ball.
 */
import { oversNotation, requiredRunRate, runRate } from "@/lib/cricket";
import type { Timeline, TimelineDelivery, TimelineInnings } from "@/lib/api/types";

export interface BatterLine {
  id: string;
  runs: number;
  balls: number;
  fours: number;
  sixes: number;
  isOut: boolean;
  dismissal: string | null;
}

export interface BowlerLine {
  id: string;
  legalBalls: number;
  runs: number;
  wickets: number;
  maidens: number;
  wides: number;
  noballs: number;
}

export interface Frame {
  index: number;
  delivery: TimelineDelivery;
  innings: TimelineInnings;
  runs: number;
  wickets: number;
  legalBalls: number;
  striker: BatterLine;
  nonStriker: BatterLine;
  bowler: BowlerLine;
  partnership: { runs: number; balls: number };
  thisOver: TimelineDelivery[];
  commentary: string;
  isInningsEnd: boolean;
}

// --------------------------------------------------------------------------- naming

export function playerName(timeline: Timeline, id: string): string {
  return timeline.players[id]?.name ?? id;
}

export function dismissalText(timeline: Timeline, delivery: TimelineDelivery): string | null {
  const wicket = delivery.wicket;
  if (!wicket) return null;
  const bowler = playerName(timeline, delivery.bowler_id);
  const fielders = wicket.fielder_ids.map((id) => playerName(timeline, id));
  const fielder = fielders[0];
  switch (wicket.kind) {
    case "caught":
      return fielder === bowler ? `c & b ${bowler}` : `c ${fielder ?? "?"} b ${bowler}`;
    case "caught and bowled":
      return `c & b ${bowler}`;
    case "bowled":
      return `b ${bowler}`;
    case "lbw":
      return `lbw b ${bowler}`;
    case "stumped":
      return `st ${fielder ?? "?"} b ${bowler}`;
    case "hit wicket":
      return `hit wicket b ${bowler}`;
    case "run out":
      return fielders.length ? `run out (${fielders.join(" / ")})` : "run out";
    default:
      return wicket.kind;
  }
}

/** One-line ball commentary, e.g. "Bumrah to Watson, FOUR". */
export function describeDelivery(timeline: Timeline, d: TimelineDelivery): string {
  const who = `${playerName(timeline, d.bowler_id)} to ${playerName(timeline, d.batter_id)}`;
  const parts: string[] = [];
  if (d.wicket) {
    const out = playerName(timeline, d.wicket.player_out_id);
    parts.push(
      d.wicket.is_dismissal
        ? `OUT! ${out} ${dismissalText(timeline, d)}`
        : `${out} ${d.wicket.kind}`,
    );
  }
  if (d.is_six) parts.push("SIX");
  else if (d.is_four) parts.push("FOUR");
  else if (d.wides) parts.push(d.wides > 1 ? `${d.wides} wides` : "wide");
  else if (d.noballs) {
    parts.push(d.runs_batter ? `no-ball, ${d.runs_batter} off the bat` : "no-ball");
  } else if (d.byes) parts.push(`${d.byes} bye${d.byes > 1 ? "s" : ""}`);
  else if (d.legbyes) parts.push(`${d.legbyes} leg bye${d.legbyes > 1 ? "s" : ""}`);
  else if (!d.wicket) {
    parts.push(
      d.runs_batter === 0 ? "no run" : `${d.runs_batter} run${d.runs_batter > 1 ? "s" : ""}`,
    );
  }
  if (d.penalty) parts.push(`${d.penalty} penalty runs`);
  return `${who}, ${parts.join(", ")}`;
}

/** Short label for a ball chip: "4", "6", "W", "•", "1wd", "2lb", ... */
export function ballChip(d: TimelineDelivery): string {
  if (d.wicket?.is_dismissal) return "W";
  if (d.is_six) return "6";
  if (d.is_four) return "4";
  if (d.wides) return `${d.wides > 1 ? d.wides : ""}wd`;
  if (d.noballs) return `${d.runs_batter || ""}nb`;
  if (d.byes) return `${d.byes}b`;
  if (d.legbyes) return `${d.legbyes}lb`;
  return d.runs_total === 0 ? "•" : String(d.runs_total);
}

// --------------------------------------------------------------------------- frames

function newBatter(id: string): BatterLine {
  return { id, runs: 0, balls: 0, fours: 0, sixes: 0, isOut: false, dismissal: null };
}

function newBowler(id: string): BowlerLine {
  return { id, legalBalls: 0, runs: 0, wickets: 0, maidens: 0, wides: 0, noballs: 0 };
}

/** Runs charged to the bowler: off the bat, wides and no-balls (not byes, leg-byes, penalties). */
export function bowlerConceded(d: TimelineDelivery): number {
  return d.runs_batter + d.wides + d.noballs;
}

interface InningsAccumulator {
  batters: Map<string, BatterLine>;
  bowlers: Map<string, BowlerLine>;
  partnership: { runs: number; balls: number };
  overKey: string;
  overBalls: TimelineDelivery[];
  overConceded: Map<string, { legal: number; conceded: number }>;
}

function accumulate(acc: InningsAccumulator, d: TimelineDelivery, timeline: Timeline): void {
  const batter = acc.batters.get(d.batter_id) ?? newBatter(d.batter_id);
  acc.batters.set(d.batter_id, batter);
  if (!acc.batters.has(d.non_striker_id)) {
    acc.batters.set(d.non_striker_id, newBatter(d.non_striker_id));
  }
  const bowler = acc.bowlers.get(d.bowler_id) ?? newBowler(d.bowler_id);
  acc.bowlers.set(d.bowler_id, bowler);

  batter.runs += d.runs_batter;
  if (!d.wides) batter.balls += 1;
  if (d.is_four) batter.fours += 1;
  if (d.is_six) batter.sixes += 1;

  bowler.runs += bowlerConceded(d);
  if (d.is_legal) bowler.legalBalls += 1;
  if (d.wides) bowler.wides += 1;
  if (d.noballs) bowler.noballs += 1;

  const overKey = `${d.over_no}`;
  if (overKey !== acc.overKey) {
    acc.overKey = overKey;
    acc.overBalls = [];
    acc.overConceded = new Map();
  }
  acc.overBalls.push(d);
  const spell = acc.overConceded.get(d.bowler_id) ?? { legal: 0, conceded: 0 };
  spell.legal += d.is_legal ? 1 : 0;
  spell.conceded += bowlerConceded(d);
  acc.overConceded.set(d.bowler_id, spell);
  if (spell.legal === 6 && d.is_legal && spell.conceded === 0) bowler.maidens += 1;

  acc.partnership.runs += d.runs_total;
  if (d.is_legal) acc.partnership.balls += 1;

  if (d.wicket) {
    const out = acc.batters.get(d.wicket.player_out_id) ?? newBatter(d.wicket.player_out_id);
    acc.batters.set(out.id, out);
    if (d.wicket.is_dismissal) {
      out.isOut = true;
      out.dismissal = dismissalText(timeline, d);
      if (d.wicket.bowler_credited) bowler.wickets += 1;
      acc.partnership = { runs: 0, balls: 0 };
    } else {
      out.dismissal = d.wicket.kind;
    }
  }
}

function emptyAccumulator(): InningsAccumulator {
  return {
    batters: new Map(),
    bowlers: new Map(),
    partnership: { runs: 0, balls: 0 },
    overKey: "",
    overBalls: [],
    overConceded: new Map(),
  };
}

/** Precompute the match state after every delivery. O(n); run once per match. */
export function buildFrames(timeline: Timeline): Frame[] {
  const inningsByNo = new Map(timeline.innings.map((i) => [i.innings_no, i]));
  const frames: Frame[] = [];
  let acc = emptyAccumulator();
  let currentInnings = -1;

  timeline.deliveries.forEach((d, index) => {
    if (d.innings_no !== currentInnings) {
      acc = emptyAccumulator();
      currentInnings = d.innings_no;
    }
    accumulate(acc, d, timeline);
    const next = timeline.deliveries[index + 1];
    frames.push({
      index,
      delivery: d,
      innings: inningsByNo.get(d.innings_no)!,
      runs: d.team_runs,
      wickets: d.team_wickets,
      legalBalls: d.legal_ball_no,
      striker: { ...acc.batters.get(d.batter_id)! },
      nonStriker: { ...acc.batters.get(d.non_striker_id)! },
      bowler: { ...acc.bowlers.get(d.bowler_id)! },
      partnership: { ...acc.partnership },
      thisOver: [...acc.overBalls],
      commentary: describeDelivery(timeline, d),
      isInningsEnd: !next || next.innings_no !== d.innings_no,
    });
  });
  return frames;
}

// --------------------------------------------------------------------------- scoreboard

export interface ScoreState {
  innings: TimelineInnings;
  runs: number;
  wickets: number;
  overs: string;
  runRate: number | null;
  target: number | null;
  runsNeeded: number | null;
  ballsRemaining: number | null;
  requiredRate: number | null;
}

export function scoreState(frame: Frame): ScoreState {
  const { innings, runs, wickets, legalBalls } = frame;
  const target = innings.target_runs ?? null;
  const runsNeeded = target !== null ? Math.max(target - runs, 0) : null;
  // A Test innings has no over limit, so no balls remaining.
  const ballsRemaining =
    target !== null && innings.max_balls !== null
      ? Math.max(innings.max_balls - legalBalls, 0)
      : null;
  return {
    innings,
    runs,
    wickets,
    overs: oversNotation(legalBalls),
    runRate: runRate(runs, legalBalls),
    target,
    runsNeeded,
    ballsRemaining,
    requiredRate:
      runsNeeded !== null && ballsRemaining !== null
        ? requiredRunRate(runsNeeded, ballsRemaining)
        : null,
  };
}

// --------------------------------------------------------------------------- live scorecard

export interface LiveInningsCard {
  innings: TimelineInnings;
  runs: number;
  wickets: number;
  overs: string;
  extras: number;
  batting: BatterLine[];
  bowling: BowlerLine[];
  complete: boolean;
}

/** Scorecards for every innings started by the cursor, as they stood at that ball. */
export function scorecardAt(timeline: Timeline, cursor: number): LiveInningsCard[] {
  const cards: LiveInningsCard[] = [];
  let acc = emptyAccumulator();
  let order: string[] = [];
  let extras = 0;
  let last: TimelineDelivery | null = null;

  const close = (complete: boolean) => {
    if (!last) return;
    const innings = timeline.innings.find((i) => i.innings_no === last!.innings_no)!;
    cards.push({
      innings,
      runs: last.team_runs,
      wickets: last.team_wickets,
      overs: oversNotation(last.legal_ball_no),
      extras,
      batting: order.map((id) => acc.batters.get(id)!),
      bowling: [...acc.bowlers.values()],
      complete,
    });
  };

  for (let i = 0; i <= cursor && i < timeline.deliveries.length; i++) {
    const d = timeline.deliveries[i];
    if (last && d.innings_no !== last.innings_no) {
      close(true);
      acc = emptyAccumulator();
      order = [];
      extras = 0;
    }
    for (const id of [d.batter_id, d.non_striker_id]) {
      if (!order.includes(id)) order.push(id);
    }
    accumulate(acc, d, timeline);
    extras += d.runs_extras;
    last = d;
  }
  const next = timeline.deliveries[cursor + 1];
  close(!next || (last !== null && next.innings_no !== last.innings_no));
  return cards;
}

// --------------------------------------------------------------------------- charts

export interface OverPoint {
  over: number; // 1-based
  runs: number;
  wickets: number;
}

/** Runs and wickets per over for one innings, up to the cursor. */
export function oversUpTo(timeline: Timeline, inningsNo: number, cursor: number): OverPoint[] {
  const overs = new Map<number, OverPoint>();
  timeline.deliveries.forEach((d, i) => {
    if (i > cursor || d.innings_no !== inningsNo) return;
    const point = overs.get(d.over_no) ?? { over: d.over_no + 1, runs: 0, wickets: 0 };
    point.runs += d.runs_total;
    if (d.wicket?.is_dismissal) point.wickets += 1;
    overs.set(d.over_no, point);
  });
  return [...overs.values()].sort((a, b) => a.over - b.over);
}

export interface WormPoint {
  ball: number; // legal balls bowled
  runs: number;
}

/** Cumulative score by legal ball for one innings, up to the cursor. */
export function wormUpTo(timeline: Timeline, inningsNo: number, cursor: number): WormPoint[] {
  const points: WormPoint[] = [{ ball: 0, runs: 0 }];
  timeline.deliveries.forEach((d, i) => {
    if (i > cursor || d.innings_no !== inningsNo) return;
    const lastPoint = points[points.length - 1];
    if (d.legal_ball_no === lastPoint.ball) lastPoint.runs = d.team_runs;
    else points.push({ ball: d.legal_ball_no, runs: d.team_runs });
  });
  return points;
}

// --------------------------------------------------------------------------- navigation

/** Index of the first delivery of each over, for the "jump to over" control. */
export function overStarts(
  timeline: Timeline,
): { inningsNo: number; over: number; index: number }[] {
  const starts: { inningsNo: number; over: number; index: number }[] = [];
  timeline.deliveries.forEach((d, index) => {
    const prev = timeline.deliveries[index - 1];
    if (!prev || prev.innings_no !== d.innings_no || prev.over_no !== d.over_no) {
      starts.push({ inningsNo: d.innings_no, over: d.over_no + 1, index });
    }
  });
  return starts;
}

/** Indices of dismissals, for jumping between key moments. */
export function wicketIndices(timeline: Timeline): number[] {
  return timeline.deliveries.flatMap((d, i) => (d.wicket?.is_dismissal ? [i] : []));
}
