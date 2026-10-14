import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BottomNav } from "@/components/layout/bottom-nav";

vi.mock("next/navigation", () => ({ usePathname: () => "/bbl/players" }));

describe("BottomNav", () => {
  it("links the four most-used pages of the competition and opens the rest", () => {
    render(<BottomNav />);
    const bar = screen.getByRole("navigation", { name: "Quick" });
    const links = within(bar).getAllByRole("link");
    expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["Overview", "/bbl"],
      ["Matches", "/bbl/matches"],
      ["Players", "/bbl/players"],
      ["Teams", "/bbl/teams"],
    ]);
    expect(within(bar).getByRole("link", { name: "Players" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(bar).getByRole("button", { name: "Open navigation" })).toBeInTheDocument();
  });
});
