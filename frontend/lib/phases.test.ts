import { describe, expect, it } from "vitest";

import { fig, inningsChoices, maxInnings, oversLabel, phaseColor, phaseQuery } from "@/lib/phases";

describe("phase analysis helpers", () => {
  it("passes good filters to the API", () => {
    const q = phaseQuery(
      { from: "2015", to: "2020", team: "MI", venue: "wankhede", innings: "2", min_balls: "60" },
      "T20",
    );
    expect(q.toString()).toBe("from=2015&to=2020&team=MI&venue=wankhede&innings=2&min_balls=60");
  });

  it("drops malformed or impossible filters", () => {
    expect(
      phaseQuery(
        {
          from: "2020",
          to: "2010",
          team: "M I'",
          innings: "3",
          min_balls: "0",
          venue: "x".repeat(81),
        },
        "T20",
      ).toString(),
    ).toBe("");
    expect(phaseQuery({ from: "20x0", innings: ["9", "1"] }, "ODI").toString()).toBe("");
  });

  it("lets a Test filter to any of its four innings", () => {
    expect(phaseQuery({ innings: "4" }, "Test").toString()).toBe("innings=4");
    expect(maxInnings("Test")).toBe(4);
    expect(inningsChoices("Test").map((c) => c.label)).toEqual([
      "1st innings",
      "2nd innings",
      "3rd innings",
      "4th innings",
    ]);
    expect(inningsChoices("T20").map((c) => c.label)).toEqual(["Batting first", "Chasing"]);
  });

  it("labels overs and figures", () => {
    expect(oversLabel(1, 6)).toBe("Overs 1–6");
    expect(oversLabel(81, null)).toBe("Overs 81 onwards");
    expect(fig(8.0934)).toBe("8.09");
    expect(fig(null)).toBe("—");
    expect(phaseColor(0)).toBe("var(--chart-1)");
    expect(phaseColor(5)).toBe("var(--chart-1)");
  });
});
