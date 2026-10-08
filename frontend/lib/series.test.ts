import { describe, expect, it } from "vitest";

import type { SeriesSummary } from "@/lib/api/types";

import { dateRange, groupTournaments, kindLabel, seriesNotes, seriesTitle } from "./series";

function series(overrides: Partial<SeriesSummary> = {}): SeriesSummary {
  return {
    event_id: "2005-the-ashes",
    name: "The Ashes",
    season: "2005",
    kind: "series",
    tournament_id: null,
    named: true,
    start_date: "2005-07-21",
    end_date: "2005-09-12",
    matches: 5,
    missing: 0,
    teams: [],
    drawn: 2,
    tied: 0,
    no_result: 0,
    champion: null,
    runner_up: null,
    recent: false,
    result_text: "England won 2–1, 2 drawn",
    ...overrides,
  };
}

describe("series", () => {
  it("titles a series by its name and season", () => {
    expect(seriesTitle(series())).toBe("The Ashes 2005");
    expect(seriesTitle(series({ name: "Asia Cup 2023", season: "2023" }))).toBe("Asia Cup 2023");
  });

  it("dates a one-day event once", () => {
    expect(dateRange("2005-07-21", "2005-09-12")).toContain("–");
    expect(dateRange("2023-11-19", "2023-11-19")).not.toContain("–");
  });

  it("counts a series' length with the matches the data is missing", () => {
    expect(kindLabel(series(), "Test")).toBe("5-Test series");
    expect(kindLabel(series({ matches: 3, missing: 1 }), "Test")).toBe("4-Test series");
    expect(kindLabel(series({ matches: 1 }), "ODI")).toBe("One ODI");
    expect(kindLabel(series({ kind: "tournament" }), "T20")).toBe("Tournament");
  });

  it("orders major tournaments with the World Cups first", () => {
    const groups = groupTournaments([
      series({ event_id: "a", tournament_id: "asia-cup-odi", name: "Asia Cup" }),
      series({ event_id: "b", tournament_id: "cricket-world-cup", start_date: "2019-05-30" }),
      series({ event_id: "c", tournament_id: "cricket-world-cup", start_date: "2023-10-05" }),
      series({ event_id: "d", tournament_id: null }),
    ]);
    expect(groups.map((g) => g.id)).toEqual(["cricket-world-cup", "asia-cup-odi"]);
    expect(groups[0].editions.map((e) => e.event_id)).toEqual(["c", "b"]);
  });

  it("explains unfinished, incomplete and unnamed series", () => {
    expect(seriesNotes(series())).toEqual([]);
    const notes = seriesNotes(series({ recent: true, missing: 1, named: false }));
    expect(notes).toHaveLength(3);
    expect(notes[1]).toContain("One match of this series is not in the data");
  });
});
