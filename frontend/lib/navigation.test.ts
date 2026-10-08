import { describe, expect, it } from "vitest";

import {
  PRIMARY_NAV,
  SECONDARY_NAV,
  isActive,
  isAvailable,
  isShown,
  navHref,
} from "@/lib/navigation";

const byLabel = (label: string) =>
  [...PRIMARY_NAV, ...SECONDARY_NAV].find((i) => i.label === label)!;
const overview = byLabel("Overview");
const matches = byLabel("Matches");
const lab = byLabel("Analytics Lab");
const about = byLabel("About & Methodology");

describe("navigation", () => {
  it("has unique pages", () => {
    const paths = [...PRIMARY_NAV, ...SECONDARY_NAV].map((i) => `${i.scope}:${i.path}`);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("only exposes pages from shipped milestones", () => {
    for (const item of [...PRIMARY_NAV, ...SECONDARY_NAV]) expect(isAvailable(item)).toBe(true);
  });

  it("links pages within the competition being browsed", () => {
    expect(navHref(overview, "ipl")).toBe("/ipl");
    expect(navHref(matches, "t20i")).toBe("/t20i/matches");
    // Global pages are the same everywhere.
    expect(navHref(about, "bbl")).toBe("/about");
  });

  it("shows the Analytics Lab only where it has notes", () => {
    expect(isShown(lab, "ipl")).toBe(true);
    expect(isShown(lab, "t20i")).toBe(false);
    expect(isShown(matches, "t20i")).toBe(true);
  });

  it("offers Tests a chase calculator instead of the simulator", () => {
    const simulator = byLabel("Simulator");
    const chase = byLabel("Chase calculator");
    expect(isShown(simulator, "ipl")).toBe(true);
    expect(isShown(simulator, "test")).toBe(false);
    expect(isShown(chase, "test")).toBe(true);
    expect(isShown(chase, "odi")).toBe(false);
  });

  it("matches the overview exactly", () => {
    expect(isActive(overview, "/ipl", "ipl")).toBe(true);
    expect(isActive(overview, "/ipl/matches", "ipl")).toBe(false);
  });

  it("treats nested pages as active", () => {
    expect(isActive(matches, "/t20i/matches", "t20i")).toBe(true);
    expect(isActive(matches, "/t20i/matches/1082591", "t20i")).toBe(true);
    expect(isActive(matches, "/t20i/matchesfoo", "t20i")).toBe(false);
    expect(isActive(about, "/about", "ipl")).toBe(true);
  });
});
