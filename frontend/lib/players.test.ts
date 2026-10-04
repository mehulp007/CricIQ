import { describe, expect, it } from "vitest";

import {
  dismissalLabel,
  formatRatingValue,
  isBetter,
  ordinal,
  parseSeason,
  ratingBand,
  roleLabel,
  seasonRanges,
  signed,
} from "./players";

describe("player formatting", () => {
  it("signs values with a true minus and no negative zero", () => {
    expect(signed(3.42)).toBe("+3.4");
    expect(signed(-0.54)).toBe("−0.5");
    expect(signed(-0.04)).toBe("0.0");
    expect(signed(2.645, 2)).toBe("+2.65");
  });

  it("writes ordinals", () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 61, 100].map(ordinal)).toEqual([
      "1st",
      "2nd",
      "3rd",
      "4th",
      "11th",
      "12th",
      "13th",
      "21st",
      "22nd",
      "61st",
      "100th",
    ]);
  });

  it("compresses seasons into ranges", () => {
    expect(seasonRanges([2010, 2008, 2009, 2014, 2016, 2015])).toBe("2008–2010, 2014–2016");
    expect(seasonRanges([2019])).toBe("2019");
    expect(seasonRanges([])).toBe("");
  });

  it("formats rating estimates by unit", () => {
    expect(formatRatingValue(3.4, "runs_per_100")).toBe("+3.4 runs per 100 balls");
    expect(formatRatingValue(-0.49, "runs_per_over")).toBe("−0.49 runs saved per over");
    expect(formatRatingValue(1.27, "dismissals_per_100")).toBe(
      "+1.27 dismissals avoided per 100 balls",
    );
    expect(formatRatingValue(0.14, "wickets_per_4_overs")).toBe("+0.14 wickets per 4 overs");
    expect(formatRatingValue(42.37, "percent")).toBe("42% of innings");
    expect(formatRatingValue(1.53, "points")).toBe("+1.5 pts per innings");
    expect(formatRatingValue(null, "points")).toBe("—");
  });

  it("describes ratings in words", () => {
    expect([95, 75, 50, 12, 3].map(ratingBand)).toEqual([
      "Elite",
      "Strong",
      "Average",
      "Weak",
      "Poor",
    ]);
  });

  it("knows which direction is better", () => {
    expect(isBetter(2, true)).toBe(true);
    expect(isBetter(-0.5, false)).toBe(true);
    expect(isBetter(0.5, false)).toBe(false);
  });

  it("labels roles and dismissals", () => {
    expect(roleLabel("batter", true)).toBe("Wicketkeeper-batter");
    expect(roleLabel("all_rounder", false)).toBe("All-rounder");
    expect(dismissalLabel("lbw")).toBe("LBW");
    expect(dismissalLabel("handled the ball")).toBe("Handled the ball");
  });

  it("parses season params", () => {
    expect(parseSeason("2019")).toBe(2019);
    expect(parseSeason(["2020", "2021"])).toBe(2020);
    expect(parseSeason("abc")).toBeUndefined();
    expect(parseSeason("1999")).toBeUndefined();
    expect(parseSeason(undefined)).toBeUndefined();
  });
});
