import { describe, expect, it } from "vitest";

import final2019 from "@/data/featured/1181768.json";
import opener2008 from "@/data/featured/335982.json";
import doubleSuperOver from "@/data/featured/1216517.json";
import type { Timeline } from "@/lib/api/types";

import {
  ballChip,
  buildFrames,
  describeDelivery,
  oversUpTo,
  overStarts,
  scoreState,
  scorecardAt,
  wicketIndices,
  wormUpTo,
} from "./engine";

const final = final2019 as unknown as Timeline;
const opener = opener2008 as unknown as Timeline;
const superOvers = doubleSuperOver as unknown as Timeline;

const frames = buildFrames(final);

describe("buildFrames", () => {
  it("creates one frame per delivery and ends on the final score", () => {
    expect(frames).toHaveLength(final.deliveries.length);
    const last = frames[frames.length - 1];
    expect([last.runs, last.wickets]).toEqual([148, 7]);
    expect(last.isInningsEnd).toBe(true);
  });

  it("tracks individual batting to the real scorecard", () => {
    // Shane Watson made 80 off 59 in the 2019 final.
    const watsonId = Object.entries(final.players).find(([, p]) => p.name === "SR Watson")![0];
    const lastWatson = [...frames]
      .reverse()
      .find((f) => f.striker.id === watsonId || f.nonStriker.id === watsonId)!;
    const line = lastWatson.striker.id === watsonId ? lastWatson.striker : lastWatson.nonStriker;
    expect([line.runs, line.balls, line.isOut]).toEqual([80, 59, true]);
  });

  it("marks exactly one innings break in a two-innings match", () => {
    expect(frames.filter((f) => f.isInningsEnd)).toHaveLength(2);
  });

  it("resets the partnership after a dismissal", () => {
    const wicket = frames.find((f) => f.delivery.wicket?.is_dismissal)!;
    expect(wicket.partnership).toEqual({ runs: 0, balls: 0 });
  });
});

describe("scoreState", () => {
  it("computes the chase equation", () => {
    const chase = frames.find((f) => f.innings.innings_no === 2 && f.legalBalls === 114)!;
    const state = scoreState(chase);
    expect(state.target).toBe(150);
    expect(state.ballsRemaining).toBe(6);
    expect(state.runsNeeded).toBe(150 - chase.runs);
    expect(state.requiredRate).toBeCloseTo((state.runsNeeded! * 6) / 6, 5);
  });

  it("has no chase equation in the first innings", () => {
    expect(scoreState(frames[10]).target).toBeNull();
  });
});

describe("scorecardAt", () => {
  it("reproduces the full scorecard at the last ball", () => {
    const cards = scorecardAt(opener, opener.deliveries.length - 1);
    expect(cards.map((c) => [c.runs, c.wickets, c.overs])).toEqual([
      [222, 3, "20.0"],
      [82, 10, "15.1"],
    ]);
    const mccullum = cards[0].batting.find((b) => opener.players[b.id].name === "BB McCullum")!;
    expect([mccullum.runs, mccullum.balls, mccullum.isOut]).toEqual([158, 73, false]);
    for (const card of cards) {
      const batted = card.batting.reduce((sum, b) => sum + b.runs, 0);
      expect(batted + card.extras).toBe(card.runs);
    }
  });

  it("shows only what has happened so far", () => {
    expect(scorecardAt(opener, -1)).toEqual([]);
    const early = scorecardAt(opener, 5);
    expect(early).toHaveLength(1);
    expect(early[0].complete).toBe(false);
  });

  it("credits bowlers only with what they concede", () => {
    const [first] = scorecardAt(opener, opener.deliveries.length - 1);
    const bowled = first.bowling.reduce((sum, b) => sum + b.legalBalls, 0);
    expect(bowled).toBe(120);
  });
});

describe("chart data", () => {
  it("builds a Manhattan that sums to the innings total", () => {
    const overs = oversUpTo(opener, 1, opener.deliveries.length - 1);
    expect(overs).toHaveLength(20);
    expect(overs.reduce((sum, o) => sum + o.runs, 0)).toBe(222);
  });

  it("builds a worm that ends on the score", () => {
    const worm = wormUpTo(opener, 2, opener.deliveries.length - 1);
    expect(worm[0]).toEqual({ ball: 0, runs: 0 });
    expect(worm[worm.length - 1]).toEqual({ ball: 91, runs: 82 });
  });

  it("reveals nothing beyond the cursor", () => {
    expect(oversUpTo(opener, 2, 50)).toEqual([]);
  });
});

describe("navigation", () => {
  it("lists over starts across all innings including super overs", () => {
    const starts = overStarts(superOvers);
    expect(starts.filter((s) => s.inningsNo >= 3)).toHaveLength(4);
    expect(starts[0]).toEqual({ inningsNo: 1, over: 1, index: 0 });
  });

  it("finds every dismissal", () => {
    expect(wicketIndices(final)).toHaveLength(15);
  });
});

describe("commentary", () => {
  it("describes boundaries, extras and wickets", () => {
    const four = final.deliveries.find((d) => d.is_four)!;
    expect(describeDelivery(final, four)).toMatch(/FOUR$/);
    expect(ballChip(four)).toBe("4");
    const wide = final.deliveries.find((d) => d.wides > 0)!;
    expect(ballChip(wide)).toMatch(/wd$/);
    const out = final.deliveries.find((d) => d.wicket?.is_dismissal)!;
    expect(describeDelivery(final, out)).toContain("OUT!");
    expect(ballChip(out)).toBe("W");
  });
});
