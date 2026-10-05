import { describe, expect, it } from "vitest";

import type { H2HExpectation } from "@/lib/api/types";
import {
  FINISH_RANK,
  expectationVerdict,
  finishLabel,
  formatNrr,
  h2hHref,
  parseTeamId,
  pct,
  recordText,
  seasonSpan,
} from "@/lib/teams";

describe("parseTeamId", () => {
  it("accepts franchise codes in any case", () => {
    expect(parseTeamId("mi")).toBe("MI");
    expect(parseTeamId(["PBKS", "CSK"])).toBe("PBKS");
    expect(parseTeamId(" rcb ")).toBe("RCB");
  });

  it("rejects anything else", () => {
    expect(parseTeamId(undefined)).toBeUndefined();
    expect(parseTeamId("M")).toBeUndefined();
    expect(parseTeamId("MI1")).toBeUndefined();
    expect(parseTeamId("../x")).toBeUndefined();
  });
});

describe("finishLabel", () => {
  it("names titles, finals and playoff exits", () => {
    expect(finishLabel("champion", null, 1, 10)).toBe("Champions");
    expect(finishLabel("runner_up", "Final", 2, 10)).toBe("Runners-up");
    expect(finishLabel("playoffs", "Qualifier 2", 3, 10)).toBe("Out in Qualifier 2");
    expect(finishLabel("playoffs", "Eliminator", 4, 10)).toBe("Out in the Eliminator");
    expect(finishLabel("playoffs", "3rd Place Play-Off", 4, 8)).toBe("Semi-finalists");
    expect(finishLabel("playoffs", "Something new", 4, 8)).toBe("Playoffs");
  });

  it("gives the league position otherwise", () => {
    expect(finishLabel("league", null, 6, 10)).toBe("6th of 10");
    expect(finishLabel("league", null, 1, 8)).toBe("1st of 8");
  });

  it("ranks finishes best first", () => {
    const order = (["league", "champion", "playoffs", "runner_up"] as const)
      .slice()
      .sort((a, b) => FINISH_RANK[a] - FINISH_RANK[b]);
    expect(order).toEqual(["champion", "runner_up", "playoffs", "league"]);
  });
});

describe("formatting", () => {
  it("formats records, percentages and net run rate", () => {
    expect(recordText({ won: 148, lost: 117, no_result: 0 })).toBe("148–117");
    expect(recordText({ won: 9, lost: 4, no_result: 1 })).toBe("9–4 · 1 NR");
    expect(pct(55.8)).toBe("55.8%");
    expect(pct(null)).toBe("—");
    expect(formatNrr(0.421)).toBe("+0.421");
    expect(formatNrr(-0.011)).toBe("−0.011");
    expect(formatNrr(0)).toBe("0.000");
    expect(formatNrr(undefined)).toBe("—");
    expect(seasonSpan(2008, 2026)).toBe("2008–2026");
    expect(seasonSpan(2011, 2011)).toBe("2011");
  });

  it("builds head-to-head links with an optional window", () => {
    expect(h2hHref("MI", "CSK")).toBe("/teams/h2h?a=MI&b=CSK");
    expect(h2hHref("MI", "CSK", { from: 2018, to: 2020 })).toBe(
      "/teams/h2h?a=MI&b=CSK&from=2018&to=2020",
    );
  });
});

describe("expectationVerdict", () => {
  const base: H2HExpectation = {
    decided: 37,
    a_won: 19,
    a_expected: 18.6,
    low: 13.7,
    high: 23.6,
    seasons_used: 19,
  };

  it("calls a record inside the chance range no hold", () => {
    expect(expectationVerdict(base, "MI", "KKR")).toMatch(/^Within the range chance/);
    expect(expectationVerdict(base, "MI", "KKR")).toMatch(/no sign of a hold/);
  });

  it("names the side beating form, without calling it a forecast", () => {
    const high = expectationVerdict({ ...base, a_won: 25 }, "MI", "KKR");
    expect(high).toMatch(/^MI have beaten form by 6\.4 wins/);
    expect(high).toMatch(/do not predict the next meeting/);
    const low = expectationVerdict({ ...base, a_won: 12 }, "MI", "KKR");
    expect(low).toMatch(/^KKR have beaten form/);
  });
});
