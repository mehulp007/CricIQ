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

  it("does not link to pages that have not shipped", () => {
    renderNav();
    expect(screen.getByRole("link", { name: "Matches" })).toHaveAttribute("href", "/matches");
    expect(screen.getByRole("link", { name: "Players" })).toHaveAttribute("href", "/players");
    expect(screen.getByRole("link", { name: "Matchups" })).toHaveAttribute("href", "/matchups");
    expect(screen.queryByRole("link", { name: /Compare/ })).not.toBeInTheDocument();
    expect(screen.getByText("Compare").closest("[aria-disabled]")).toBeInTheDocument();
  });
});
