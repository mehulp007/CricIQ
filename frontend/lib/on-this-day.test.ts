import { describe, expect, it } from "vitest";

import {
  allDays,
  dateSlug,
  dayLabel,
  daysIn,
  filterEntries,
  mergeEntries,
  parseDateSlug,
  shiftDay,
  todayIn,
  type DatedEntry,
} from "@/lib/on-this-day";

const entry = (over: Partial<DatedEntry>): DatedEntry => ({
  match_id: 1,
  date: "2019-05-12",
  year: 2019,
  season: 2019,
  stage: "League",
  is_playoff: false,
  teams: [
    { franchise_id: "MI", name: "Mumbai Indians", color: "#004BA0" },
    { franchise_id: "CSK", name: "Chennai Super Kings", color: "#F9CD05" },
  ],
  venue: null,
  result: "Mumbai Indians won by 1 run",
  headline: "x",
  highlight: null,
  batting: null,
  bowling: null,
  player_of_match: [],
  swing: null,
  notability: 0,
  competition: "ipl",
  label: "IPL",
  format: "T20",
  ...over,
});

describe("on this day dates", () => {
  it("writes and reads date slugs", () => {
    expect(dateSlug({ month: 11, day: 5 })).toBe("november-5");
    expect(parseDateSlug("november-5")).toEqual({ month: 11, day: 5 });
    expect(parseDateSlug("February-29")).toEqual({ month: 2, day: 29 });
    for (const bad of ["november-31", "february-30", "smarch-1", "november", "11-5", "june-0"]) {
      expect(parseDateSlug(bad)).toBeNull();
    }
    expect(dayLabel({ month: 2, day: 29 })).toBe("29 February");
  });

  it("knows every month's length, with 29 February", () => {
    expect([1, 2, 4, 12].map(daysIn)).toEqual([31, 29, 30, 31]);
    expect(allDays()).toHaveLength(366);
  });

  it("steps round the year", () => {
    expect(shiftDay({ month: 12, day: 31 }, 1)).toEqual({ month: 1, day: 1 });
    expect(shiftDay({ month: 1, day: 1 }, -1)).toEqual({ month: 12, day: 31 });
    expect(shiftDay({ month: 2, day: 28 }, 1)).toEqual({ month: 2, day: 29 });
    expect(shiftDay({ month: 3, day: 1 }, -1)).toEqual({ month: 2, day: 29 });
  });

  it("finds today in a time zone", () => {
    // 20:00 UTC on 4 November is already 5 November in India.
    const late = new Date(Date.UTC(2026, 10, 4, 20, 0));
    expect(todayIn("Asia/Kolkata", late)).toEqual({ month: 11, day: 5 });
    expect(todayIn("America/New_York", late)).toEqual({ month: 11, day: 4 });
  });

  it("merges competitions, most notable first, then the most recent", () => {
    const merged = mergeEntries([
      [entry({ match_id: 1, notability: 1, date: "2010-11-05" })],
      [
        entry({ match_id: 2, notability: 4, date: "2003-11-05", competition: "odi" }),
        entry({ match_id: 3, notability: 1, date: "2021-11-05", competition: "t20i" }),
      ],
    ]);
    expect(merged.map((e) => e.match_id)).toEqual([2, 3, 1]);
  });

  it("filters by competition, format and side", () => {
    const entries = [
      entry({ match_id: 1 }),
      entry({ match_id: 2, competition: "test", format: "Test", teams: [] }),
    ];
    expect(filterEntries(entries, { competition: "test" }).map((e) => e.match_id)).toEqual([2]);
    expect(filterEntries(entries, { format: "T20" }).map((e) => e.match_id)).toEqual([1]);
    expect(filterEntries(entries, { team: "Mumbai Indians" }).map((e) => e.match_id)).toEqual([1]);
    expect(filterEntries(entries, {})).toHaveLength(2);
  });
});
