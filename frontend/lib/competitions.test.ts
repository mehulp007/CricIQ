import { describe, expect, it } from "vitest";

import {
  COMPETITIONS,
  competitionOf,
  competitionPath,
  isCompetitionId,
  seasonLabel,
  switchPath,
} from "@/lib/competitions";

describe("competitions", () => {
  it("lists the six served competitions once each", () => {
    const ids = COMPETITIONS.map((c) => c.id);
    expect(ids).toEqual(["ipl", "t20i", "bbl", "psl", "cpl", "sa20"]);
    expect(isCompetitionId("t20i")).toBe(true);
    expect(isCompetitionId("odi")).toBe(false);
    expect(isCompetitionId(undefined)).toBe(false);
  });

  it("builds and reads competition paths", () => {
    expect(competitionPath("bbl")).toBe("/bbl");
    expect(competitionPath("bbl", "/")).toBe("/bbl");
    expect(competitionPath("t20i", "/players/abc")).toBe("/t20i/players/abc");
    expect(competitionOf("/t20i/matches/1")).toBe("t20i");
    expect(competitionOf("/about")).toBeNull();
    expect(competitionOf("/")).toBeNull();
  });

  it("keeps the same kind of page when switching", () => {
    expect(switchPath("/ipl/matches", "t20i")).toBe("/t20i/matches");
    expect(switchPath("/ipl", "psl")).toBe("/psl");
    expect(switchPath("/ipl/teams/h2h", "bbl")).toBe("/bbl/teams/h2h");
    // One match, player or team has no counterpart elsewhere: go to the list.
    expect(switchPath("/ipl/matches/1181768", "t20i")).toBe("/t20i/matches");
    expect(switchPath("/ipl/players/ba607b88", "bbl")).toBe("/bbl/players");
    expect(switchPath("/ipl/teams/MI", "t20i")).toBe("/t20i/teams");
    // The Analytics Lab covers the IPL only.
    expect(switchPath("/ipl/lab/pressure", "t20i")).toBe("/t20i");
    // From a global page, to the competition's overview.
    expect(switchPath("/about", "cpl")).toBe("/cpl");
  });

  it("names seasons the competition's way", () => {
    expect(seasonLabel("bbl", 2024)).toBe("2023/24");
    expect(seasonLabel("bbl", 2000)).toBe("1999/00");
    expect(seasonLabel("ipl", 2024)).toBe("2024");
  });
});
