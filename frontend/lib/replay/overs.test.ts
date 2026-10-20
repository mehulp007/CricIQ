import { describe, expect, it } from "vitest";

import final2019 from "@/data/featured/ipl/1181768.json";
import doubleSuperOver from "@/data/featured/ipl/1216517.json";
import type { Timeline } from "@/lib/api/types";

import { oversUpTo } from "./engine";
import { describeOver, overBars } from "./overs";

const final = final2019 as unknown as Timeline;
const superOvers = doubleSuperOver as unknown as Timeline;
const end = final.deliveries.length - 1;

describe("overBars", () => {
  it("has nothing before the first ball", () => {
    expect(overBars(final, -1)).toEqual([]);
  });

  it("builds the first over ball by ball, marking it current until it is complete", () => {
    const [first] = overBars(final, 0);
    expect(first).toMatchObject({ inningsNo: 1, over: 1, startIndex: 0, current: true });
    expect(first.complete).toBe(false);
    const sixth = final.deliveries.findIndex((d) => d.over_no === 1) - 1;
    const done = overBars(final, sixth)[0];
    expect(done.complete).toBe(true);
    expect(done.current).toBe(true);
  });

  it("matches the Manhattan's runs and wickets for both innings at the end", () => {
    const bars = overBars(final, end);
    for (const inningsNo of [1, 2] as const) {
      const expected = oversUpTo(final, inningsNo, end);
      const got = bars.filter((b) => b.inningsNo === inningsNo);
      expect(got.map((b) => [b.over, b.runs, b.wickets])).toEqual(
        expected.map((p) => [p.over, p.runs, p.wickets]),
      );
      expect(got.every((b) => b.complete)).toBe(true);
    }
    // Only the last over is current.
    expect(bars.filter((b) => b.current)).toHaveLength(1);
    expect(bars.at(-1)).toMatchObject({ inningsNo: 2, over: 20, current: true });
  });

  it("seeks each over to its first ball", () => {
    for (const bar of overBars(final, end)) {
      const d = final.deliveries[bar.startIndex];
      expect([d.innings_no, d.over_no + 1]).toEqual([bar.inningsNo, bar.over]);
      const before = final.deliveries[bar.startIndex - 1];
      if (before)
        expect([before.innings_no, before.over_no]).not.toEqual([d.innings_no, d.over_no]);
    }
  });

  it("leaves super overs out", () => {
    const bars = overBars(superOvers, superOvers.deliveries.length - 1);
    expect(bars.every((b) => b.inningsNo === 1 || b.inningsNo === 2)).toBe(true);
    expect(Math.max(...bars.map((b) => b.over))).toBeLessThanOrEqual(20);
  });
});

describe("describeOver", () => {
  it("reads as a sentence", () => {
    const bar = {
      inningsNo: 1 as const,
      over: 14,
      runs: 18,
      wickets: 1,
      startIndex: 80,
      current: false,
      complete: true,
    };
    expect(describeOver(bar, "MI")).toBe("MI, over 14: 18 runs, 1 wicket");
    expect(describeOver({ ...bar, runs: 1, wickets: 0, complete: false }, "MI")).toBe(
      "MI, over 14: 1 run so far",
    );
  });
});
