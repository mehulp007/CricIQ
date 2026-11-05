import { describe, expect, it } from "vitest";

import type { RecordEntry } from "@/lib/api/types";
import {
  GROUP_LABELS,
  matchHref,
  pageOf,
  PAGE_SIZE,
  recordKeys,
  recordQuery,
  shortDate,
  whoLabel,
} from "@/lib/records";
import { toSearchParams, withParam } from "@/lib/url";

const entry = (over: Partial<RecordEntry> = {}): RecordEntry => ({
  rank: 1,
  tied: false,
  value: 372,
  display: "372",
  players: [],
  team: { franchise_id: "WI", name: "West Indies", color: "#7B0041" },
  opponent: null,
  venue: null,
  match_id: 891359,
  date: "2015-02-24",
  season: 2015,
  ball: null,
  figures: [],
  ...over,
});

describe("records helpers", () => {
  it("passes good filters and the page to the API", () => {
    const q = recordQuery(
      {
        from: "2010",
        to: "2020",
        team: "IND",
        opponent: "AUS",
        venue: "mcg",
        wicket: "3",
        page: "3",
      },
      { wicket: true },
    );
    expect(q.toString()).toBe(
      `from=2010&to=2020&team=IND&opponent=AUS&venue=mcg&wicket=3&limit=${PAGE_SIZE}&offset=${2 * PAGE_SIZE}`,
    );
  });

  it("drops malformed filters and keeps the wicket to partnerships", () => {
    expect(
      recordQuery(
        { from: "2020", to: "2010", team: "<x>", wicket: "11", page: "0" },
        { wicket: true },
      ).toString(),
    ).toBe(`limit=${PAGE_SIZE}`);
    expect(recordQuery({ wicket: "2" }, { wicket: false }).has("wicket")).toBe(false);
    expect(pageOf({ page: ["4", "9"] })).toBe(4);
    expect(pageOf({ page: "abc" })).toBe(1);
  });

  it("names who holds a record", () => {
    expect(whoLabel(entry())).toBe("West Indies");
    expect(
      whoLabel(
        entry({
          players: [
            { player_id: "a", name: "Chris Gayle", role: null },
            { player_id: "b", name: "Marlon Samuels", role: null },
          ],
        }),
      ),
    ).toBe("Chris Gayle & Marlon Samuels");
    expect(
      whoLabel(
        entry({
          players: [
            { player_id: "a", name: "Rahul Tripathi", role: "batter" },
            { player_id: "b", name: "R Ashwin", role: "bowler" },
          ],
        }),
      ),
    ).toBe("Rahul Tripathi (batting), R Ashwin (bowling)");
  });

  it("links to the match, at the ball where there is one", () => {
    expect(matchHref(entry())).toBe("/matches/891359");
    expect(matchHref(entry({ ball: "2.124" }))).toBe("/matches/891359?ball=2.124");
    expect(matchHref(entry({ match_id: null }))).toBeNull();
    expect(shortDate("2015-02-24")).toBe("24 Feb 2015");
    expect(shortDate(null)).toBe("");
  });

  it("knows each format's records and labels every group", () => {
    expect(recordKeys("T20")).toContain("most-four-wicket-innings");
    expect(recordKeys("Test")).toContain("biggest-innings-wins");
    expect(recordKeys("Test")).not.toContain("best-economy-in-an-innings");
    expect(Object.keys(GROUP_LABELS)).toHaveLength(7);
  });

  it("page links keep the filters and only drop the page for other changes", () => {
    const raw = toSearchParams({ team: "MI", page: "2", venue: ["a", "b"] });
    expect(raw.toString()).toBe("team=MI&page=2&venue=a");
    expect(withParam(raw, "page", "3").toString()).toBe("team=MI&page=3&venue=a");
    expect(withParam(raw, "team", "CSK").toString()).toBe("team=CSK&venue=a");
  });
});
