import { describe, expect, it } from "vitest";

import type { PlayerProfile, Rating, RatingGroup } from "@/lib/api/types";

import {
  ageInSeason,
  compareHref,
  compareRoles,
  headlineRows,
  parseCompare,
  ratingPairs,
  trend,
} from "./compare";

function season(year: number, batting: { balls: number; sr: number; par: number } | null) {
  return {
    season: year,
    teams: ["MI"],
    matches: 14,
    batting: batting && {
      innings: 14,
      runs: Math.round((batting.balls * batting.sr) / 100),
      balls: batting.balls,
      outs: 10,
      average: 30,
      strike_rate: batting.sr,
      par_strike_rate: batting.par,
      highest: 90,
      fifties: 3,
      hundreds: 0,
    },
    bowling: null,
  };
}

function profile(
  id: string,
  overrides: {
    role?: "batter" | "bowler" | "all_rounder";
    batting?: Partial<NonNullable<PlayerProfile["batting"]>> | null;
    bowlingBalls?: number;
    dob?: string | null;
    seasons?: ReturnType<typeof season>[];
  } = {},
): PlayerProfile {
  const batting =
    overrides.batting === null
      ? null
      : {
          innings: 100,
          runs: 3000,
          balls: 2200,
          outs: 90,
          average: 33.33,
          strike_rate: 136.36,
          par_strike_rate: 130,
          runs_above_par: 140,
          boundary_pct: 18,
          dot_pct: 33,
          fifties: 20,
          hundreds: 2,
          wpa: 1.2,
          ...overrides.batting,
        };
  return {
    player: {
      player_id: id,
      name: id,
      role: overrides.role ?? "batter",
      date_of_birth: overrides.dob === undefined ? "1988-11-05" : overrides.dob,
    },
    window: { first: 2008, last: 2026 },
    batting,
    bowling: overrides.bowlingBalls
      ? { balls: overrides.bowlingBalls, economy: 7.5, par_economy: 8 }
      : null,
    seasons: overrides.seasons ?? [],
  } as unknown as PlayerProfile;
}

describe("compare URL state", () => {
  it("parses and normalises the query", () => {
    expect(parseCompare({ a: "ba607b88", b: "740742ef", from: "2020", to: "2015" })).toEqual({
      a: "ba607b88",
      b: "740742ef",
      from: 2015,
      to: 2020,
      role: undefined,
    });
    expect(parseCompare({ a: "../etc", role: "keeping" })).toEqual({
      a: undefined,
      b: undefined,
      from: undefined,
      to: undefined,
      role: undefined,
    });
    expect(parseCompare({ role: "bowling" }).role).toBe("bowling");
  });

  it("builds links", () => {
    expect(compareHref("a1", "b2", { from: 2023, role: "bowling" })).toBe(
      "/compare?a=a1&b=b2&from=2023&role=bowling",
    );
    expect(compareHref("a1", undefined)).toBe("/compare?a=a1");
    expect(compareHref(undefined, undefined)).toBe("/compare");
  });
});

describe("roles", () => {
  it("compares what both players did, bowlers as bowlers", () => {
    const bat = profile("x");
    const allRounder = profile("y", { role: "all_rounder", bowlingBalls: 600 });
    const bowler = profile("z", { role: "bowler", bowlingBalls: 2000 });
    const bowler2 = profile("w", { role: "bowler", bowlingBalls: 1500 });
    expect(compareRoles(bat, allRounder)).toEqual({ roles: ["batting"], role: "batting" });
    expect(compareRoles(bowler, bowler2).role).toBe("bowling");
    expect(compareRoles(bowler, bowler2, "batting").role).toBe("batting");
    expect(compareRoles(bowler, profile("v", { batting: null }))).toEqual({
      roles: [],
      role: null,
    });
  });
});

describe("headline rows", () => {
  it("marks the better side only where a direction is better", () => {
    const rows = headlineRows(
      profile("a"),
      profile("b", { batting: { strike_rate: 150, runs_above_par: -20, runs: 5000 } }),
      "batting",
    );
    const by = Object.fromEntries(rows.map((r) => [r.label, r]));
    expect(by["Strike rate"].better).toBe("b");
    expect(by["Runs above par"].better).toBe("a");
    expect(by["Runs"].better).toBeNull();
    expect(by["Runs"].b).toBe("5,000");
    expect(by["50s / 100s"].a).toBe("20 / 2");
    expect(by["Average"].better).toBeNull(); // equal
  });
});

describe("ratings", () => {
  const item = (key: string, rating: number) =>
    ({ key, label: key, description: "", rating }) as unknown as Rating;
  it("pairs ratings by key, keeping one-sided rows", () => {
    const a = { items: [item("scoring", 60), item("death", 90)] } as unknown as RatingGroup;
    const b = { items: [item("scoring", 40), item("chasing", 70)] } as unknown as RatingGroup;
    const pairs = ratingPairs(a, b);
    expect(pairs.map((p) => p.key)).toEqual(["scoring", "death", "chasing"]);
    expect(pairs[0].a?.rating).toBe(60);
    expect(pairs[0].b?.rating).toBe(40);
    expect(pairs[1].b).toBeNull();
    expect(ratingPairs(null, undefined)).toEqual([]);
  });
});

describe("season trend", () => {
  it("computes age on 1 May", () => {
    expect(ageInSeason("1988-11-05", 2016)).toBe(27);
    expect(ageInSeason("1990-04-30", 2016)).toBe(26);
    expect(ageInSeason("1990-05-01", 2016)).toBe(26);
    expect(ageInSeason("1990-05-02", 2016)).toBe(25);
    expect(ageInSeason(null, 2016)).toBeNull();
  });

  it("lines up both players by season or by age, skipping tiny seasons", () => {
    const a = profile("a", {
      dob: "1988-11-05",
      seasons: [
        season(2015, { balls: 300, sr: 140, par: 130 }),
        season(2016, { balls: 10, sr: 300, par: 130 }),
      ],
    });
    const b = profile("b", {
      dob: "1990-01-01",
      seasons: [season(2016, { balls: 200, sr: 120, par: 132 })],
    });
    expect(trend(a, b, "batting", "season")).toEqual([
      { x: 2015, a: 10, b: null, aBalls: 300, bBalls: 0, aSeason: 2015 },
      { x: 2016, a: null, b: -12, aBalls: 0, bBalls: 200, bSeason: 2016 },
    ]);
    const byAge = trend(a, b, "batting", "age");
    expect(byAge.map((p) => p.x)).toEqual([26]);
    expect(byAge[0]).toMatchObject({ a: 10, b: -12, aSeason: 2015, bSeason: 2016 });
  });
});
