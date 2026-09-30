import { describe, expect, it } from "vitest";

import { PRIMARY_NAV, SECONDARY_NAV, isActive, isAvailable } from "@/lib/navigation";

const overview = PRIMARY_NAV.find((i) => i.href === "/")!;
const matches = PRIMARY_NAV.find((i) => i.href === "/matches")!;
const players = PRIMARY_NAV.find((i) => i.href === "/players")!;
const models = PRIMARY_NAV.find((i) => i.href === "/models")!;

describe("navigation", () => {
  it("has unique routes", () => {
    const hrefs = [...PRIMARY_NAV, ...SECONDARY_NAV].map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("only exposes pages from shipped milestones", () => {
    expect(isAvailable(overview)).toBe(true);
    expect(isAvailable(matches)).toBe(true);
    expect(isAvailable(models)).toBe(true);
    expect(isAvailable(players)).toBe(false);
  });

  it("matches the root route exactly", () => {
    expect(isActive(overview, "/")).toBe(true);
    expect(isActive(overview, "/matches")).toBe(false);
  });

  it("treats nested routes as active", () => {
    expect(isActive(matches, "/matches")).toBe(true);
    expect(isActive(matches, "/matches/1082591")).toBe(true);
    expect(isActive(matches, "/matchesfoo")).toBe(false);
  });
});
