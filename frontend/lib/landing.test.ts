import { describe, expect, it } from "vitest";

import { COMPETITIONS } from "@/lib/competitions";
import {
  bundledDataVersion,
  DATA_COUNTS,
  landingFacts,
  pickerGroups,
  probabilityRibbon,
} from "@/lib/landing";

describe("landing facts", () => {
  it("are counted from the same data as the bundled replays", () => {
    // If this fails, the replays were exported from newer data: recount DATA_COUNTS with them.
    expect(DATA_COUNTS.dataVersion).toBe(bundledDataVersion());
  });

  it("cover every competition and add up", () => {
    const facts = landingFacts();
    expect(DATA_COUNTS.competitions.map((c) => c.id).sort()).toEqual(
      COMPETITIONS.map((c) => c.id).sort(),
    );
    expect(facts.matches).toBe(9_912);
    expect(facts.deliveries).toBe(4_570_681);
    expect(facts.competitions).toBe(8);
    expect(facts.firstSeason).toBe(2001);
  });
});

describe("the probability ribbon", () => {
  const ribbon = probabilityRibbon();

  it("follows the 2019 IPL final from before the first ball to the last", () => {
    expect(ribbon.title).toBe("IPL 2019 final");
    expect(ribbon.href).toBe("/ipl/matches/1181768");
    expect(ribbon.result).toBe("Mumbai Indians won by 1 run");
    expect(ribbon.teamA.short).toBe("MI");
    expect(ribbon.teamB.short).toBe("CSK");
    expect(ribbon.points[0][0]).toBe(0);
    expect(ribbon.points.at(-1)?.[0]).toBe(1);
    expect(ribbon.points.at(-1)?.[1]).toBe(1);
    for (const [t, wp] of ribbon.points) {
      expect(t).toBeGreaterThanOrEqual(0);
      expect(t).toBeLessThanOrEqual(1);
      expect(wp).toBeGreaterThanOrEqual(0);
      expect(wp).toBeLessThanOrEqual(1);
    }
  });

  it("marks Pollard's six and Malinga's final over from the real balls", () => {
    const [six, over] = ribbon.moments;
    expect(six.label).toBe("Pollard's six");
    expect(six.detail).toMatch(/^Over 1[4-7]\.\d · MI \d+%$/);
    expect(over.label).toBe("Malinga's final over");
    expect(over.detail).toMatch(/^CSK need 9 off 6 · MI \d+%$/);
    expect(six.t).toBeLessThan(0.5);
    expect(over.t).toBeGreaterThan(0.9);
  });
});

describe("the picker", () => {
  it("groups the leagues and the internationals", () => {
    const groups = pickerGroups();
    expect(groups.map((g) => g.title)).toEqual(["Leagues", "Internationals"]);
    expect(groups.flatMap((g) => g.cards)).toHaveLength(8);
  });
});
