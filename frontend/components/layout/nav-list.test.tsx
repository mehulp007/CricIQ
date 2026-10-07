import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NavList } from "@/components/layout/nav-list";
import { TooltipProvider } from "@/components/ui/tooltip";

const pathname = vi.hoisted(() => ({ current: "/ipl" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

function renderNav() {
  return render(
    <TooltipProvider>
      <NavList group="primary" />
    </TooltipProvider>,
  );
}

describe("NavList", () => {
  it("marks the current page", () => {
    pathname.current = "/ipl";
    renderNav();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  });

  it("links every shipped page of the competition", () => {
    pathname.current = "/ipl/matches";
    renderNav();
    for (const [name, href] of [
      ["Matches", "/ipl/matches"],
      ["Players", "/ipl/players"],
      ["Matchups", "/ipl/matchups"],
      ["Compare", "/ipl/compare"],
      ["Teams", "/ipl/teams"],
      ["Simulator", "/ipl/simulator"],
      ["Analytics Lab", "/ipl/lab"],
    ]) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(document.querySelector("[aria-disabled]")).toBeNull();
  });

  it("follows the competition being browsed", () => {
    pathname.current = "/t20i/players/abc";
    renderNav();
    expect(screen.getByRole("link", { name: "Players" })).toHaveAttribute("href", "/t20i/players");
    expect(screen.getByRole("link", { name: "Players" })).toHaveAttribute("aria-current", "page");
    // The Analytics Lab's notes are about the IPL.
    expect(screen.queryByRole("link", { name: "Analytics Lab" })).toBeNull();
  });
});
