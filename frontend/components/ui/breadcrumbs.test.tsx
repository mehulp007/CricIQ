import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Breadcrumbs } from "@/components/ui/breadcrumbs";

vi.mock("next/navigation", () => ({ usePathname: () => "/t20i/players/x" }));

describe("Breadcrumbs", () => {
  it("starts at the competition and ends at the current page, unlinked", () => {
    render(<Breadcrumbs items={[{ label: "Players", href: "/players" }, { label: "Virat Kohli" }]} />);
    const trail = screen.getByRole("navigation", { name: "Breadcrumb" });
    const items = within(trail).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(trail).getByRole("link", { name: "T20I" })).toHaveAttribute("href", "/t20i");
    expect(within(trail).getByRole("link", { name: "Players" })).toHaveAttribute(
      "href",
      "/t20i/players",
    );
    expect(within(trail).getByText("Virat Kohli")).toHaveAttribute("aria-current", "page");
    expect(within(trail).queryByRole("link", { name: "Virat Kohli" })).toBeNull();
  });
});
