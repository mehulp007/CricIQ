import { describe, expect, it } from "vitest";

import { FIRST_SEASON, favouriteAccuracy, modelSplits, roleIn } from "@/lib/models";

describe("favouriteAccuracy", () => {
  it("counts wins for the favoured side on each side of 50%", () => {
    const bins = [
      { lower: 0.1, upper: 0.2, predicted: 0.15, observed: 0.2, count: 100 },
      { lower: 0.7, upper: 0.8, predicted: 0.75, observed: 0.7, count: 300 },
    ];
    // 80 of 100 underdogs lost, 210 of 300 favourites won.
    expect(favouriteAccuracy(bins)).toBeCloseTo(290 / 400);
    expect(favouriteAccuracy([])).toBe(0);
  });
});

describe("modelSplits", () => {
  const splits = modelSplits();

  it("covers every model with ordered, non-overlapping roles", () => {
    expect(splits.map((s) => s.key)).toEqual([
      "win-probability",
      "score-projection",
      "ball-outcome",
      "ratings",
      "simulator",
    ]);
    for (const split of splits) {
      expect(split.roles[0]).toMatchObject({ role: "train", from: FIRST_SEASON });
      expect(split.roles.at(-1)?.role).toBe("test");
      for (let i = 1; i < split.roles.length; i += 1) {
        expect(split.roles[i].from).toBe(split.roles[i - 1].to + 1);
      }
    }
  });

  it("assigns each season one role", () => {
    const wp = splits[0];
    expect(roleIn(wp, FIRST_SEASON)).toBe("train");
    expect(roleIn(wp, wp.roles.at(-1)!.to)).toBe("test");
    expect(roleIn(wp, 1999)).toBeNull();
  });
});
