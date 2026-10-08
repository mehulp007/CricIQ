import { describe, expect, it } from "vitest";

import type { Timeline, TimelineDelivery } from "@/lib/api/types";
import {
  dayAt,
  outcomeAt,
  outcomeSeries,
  situation,
  testJumps,
  testTurningPoints,
  totalsAt,
} from "@/lib/replay/test";

const A = "TEST-ENG-2005";
const B = "TEST-AUS-2005";

function ball(
  innings_no: number,
  seq_no: number,
  team_runs: number,
  wp: number,
  wp_draw: number,
  over_no = 0,
): TimelineDelivery {
  return {
    innings_no,
    seq_no,
    over_no,
    ball_label: `${over_no}.${seq_no}`,
    legal_ball_no: seq_no,
    is_legal: true,
    batter_id: "x",
    non_striker_id: "y",
    bowler_id: "z",
    runs_batter: 0,
    runs_extras: 0,
    runs_total: 0,
    wides: 0,
    noballs: 0,
    byes: 0,
    legbyes: 0,
    penalty: 0,
    is_four: false,
    is_six: false,
    team_runs,
    team_wickets: 0,
    wicket: null,
    wp,
    wp_draw,
  } as TimelineDelivery;
}

function innings(innings_no: number, batting: string, bowling: string, wp: number, draw: number) {
  return {
    innings_no,
    batting_team_id: batting,
    bowling_team_id: bowling,
    is_super_over: false,
    target_runs: null,
    target_balls: null,
    max_balls: null,
    declared: false,
    follow_on: false,
    wp_start: wp,
    draw_start: draw,
  };
}

// England 100 & 50, Australia 120 & a chase of 31.
const timeline = {
  summary: {
    team_a: { team_season_id: A, franchise_id: "ENG", name: "England" },
    team_b: { team_season_id: B, franchise_id: "AUS", name: "Australia" },
  },
  teams: {
    [A]: { team_season_id: A, franchise_id: "ENG", name: "England", color: "#000" },
    [B]: { team_season_id: B, franchise_id: "AUS", name: "Australia", color: "#fff" },
  },
  innings: [
    innings(1, A, B, 0.4, 0.3),
    innings(2, B, A, 0.4, 0.3),
    innings(3, A, B, 0.3, 0.3),
    innings(4, B, A, 0.2, 0.2),
  ],
  deliveries: [
    ball(1, 1, 50, 0.45, 0.3),
    ball(1, 2, 100, 0.5, 0.3),
    ball(2, 1, 120, 0.4, 0.3),
    ball(3, 1, 50, 0.3, 0.3, 10),
    ball(4, 1, 10, 0.2, 0.1),
    ball(4, 2, 31, 0, 0),
  ],
  days: [
    { day: 1, innings_no: 1, seq_no: 0 },
    { day: 2, innings_no: 2, seq_no: 1 },
  ],
} as unknown as Timeline;

describe("Test replays", () => {
  it("gives three chances that add up", () => {
    expect(outcomeAt(timeline, -1)).toEqual({ a: 0.4, draw: 0.3, b: expect.closeTo(0.3) });
    const end = outcomeAt(timeline, 5)!;
    expect(end).toEqual({ a: 0, draw: 0, b: 1 });
  });

  it("adds up each side's runs over the innings", () => {
    expect(totalsAt(timeline, 3)).toEqual({ a: 150, b: 120 });
    expect(situation(timeline, 2)).toBe("Australia lead by 20");
    expect(situation(timeline, 3)).toBe("England lead by 30");
    expect(situation(timeline, 4)).toBe("Australia need 21 to win");
    expect(situation(timeline, 5)).toBe("Australia have won");
  });

  it("follows the estimated days", () => {
    expect(dayAt(timeline, -1)).toBe(1);
    expect(dayAt(timeline, 1)).toBe(1);
    expect(dayAt(timeline, 2)).toBe(2);
  });

  it("lays the match out over its overs, with a point at each innings start", () => {
    const series = outcomeSeries(timeline, 5);
    expect(series.filter((p) => p.index === -1)).toHaveLength(4);
    expect(series.map((p) => p.x)).toEqual([...series.map((p) => p.x)].sort((x, y) => x - y));
  });

  it("names every jump once per ball", () => {
    const jumps = testJumps(timeline);
    expect(new Set(jumps.map((j) => j.index)).size).toBe(jumps.length);
    expect(jumps[0].label).toBe("Day 1 (est.) · Innings 1 · ENG");
  });

  it("leaves the result itself out of the turning points", () => {
    const points = testTurningPoints(timeline, 10);
    expect(points.map((p) => p.index)).not.toContain(5);
  });
});
