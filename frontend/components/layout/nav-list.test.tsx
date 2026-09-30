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
    expect(screen.queryByRole("link", { name: /Matches/ })).not.toBeInTheDocument();
    expect(screen.getByText("Matches").closest("[aria-disabled]")).toBeInTheDocument();
  });
});
