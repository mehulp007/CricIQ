import { describe, expect, it } from "vitest";

import { withVersion } from "@/lib/api/version";
import { freshnessLabel, seasonSpan } from "@/lib/freshness";

const update = {
  updated_at: "2027-04-02T06:00:00",
  new_matches: 3,
  corrected_matches: 0,
  withdrawn_matches: 0,
};

describe("freshnessLabel", () => {
  it("names the latest update and what it brought", () => {
    expect(freshnessLabel({ last_update: update, latest_match_date: "2027-04-01" })).toBe(
      "Data updated 2 Apr 2027 · 3 new matches",
    );
    expect(
      freshnessLabel({
        last_update: { ...update, new_matches: 1, corrected_matches: 2, withdrawn_matches: 1 },
        latest_match_date: "2027-04-01",
      }),
    ).toBe("Data updated 2 Apr 2027 · 1 new match · 2 corrected · 1 withdrawn");
  });

  it("falls back to how far the data reaches before any sync", () => {
    expect(freshnessLabel({ last_update: null, latest_match_date: "2026-09-17" })).toBe(
      "Data to 17 Sept 2026",
    );
    expect(freshnessLabel({ last_update: null, latest_match_date: null })).toBeNull();
  });
});

describe("seasonSpan", () => {
  it("spans the first to the latest season", () => {
    const seasons = [2008, 2027, 2019].map((year) => ({
      year,
      matches: 60,
      impact_player_rule: false,
    }));
    expect(seasonSpan({ seasons })).toBe("2008–2027");
    expect(seasonSpan({ seasons: [] })).toBeNull();
  });
});

describe("withVersion", () => {
  it("keys a request by the data version", () => {
    expect(withVersion("/api/v1/meta", null)).toBe("/api/v1/meta");
    expect(withVersion("/api/v1/players/x", "2027-04-01.ab12cd34")).toBe(
      "/api/v1/players/x?v=2027-04-01.ab12cd34",
    );
    expect(withVersion("/api/v1/matches?page=1", "v 2")).toBe("/api/v1/matches?page=1&v=v%202");
  });
});
