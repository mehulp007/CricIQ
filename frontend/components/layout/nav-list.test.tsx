import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NavList } from "@/components/layout/nav-list";
import { TooltipProvider } from "@/components/ui/tooltip";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

function renderNav() {
  return render(
    <TooltipProvider>
      <NavList group="primary" />
    </TooltipProvider>,
  );
}

describe("NavList", () => {
  it("marks the current page", () => {
    renderNav();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  });

  it("links every shipped page", () => {
    renderNav();
    for (const [name, href] of [
      ["Matches", "/matches"],
      ["Players", "/players"],
      ["Matchups", "/matchups"],
      ["Compare", "/compare"],
      ["Teams", "/teams"],
      ["Simulator", "/simulator"],
      ["Analytics Lab", "/lab"],
    ]) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(document.querySelector("[aria-disabled]")).toBeNull();
  });
});
