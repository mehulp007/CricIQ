import { render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";

describe("design-system primitives", () => {
  it("PageHeader renders the page's h1 with its description and actions", () => {
    render(
      <PageHeader
        eyebrow="IPL"
        title="Players"
        description="Every player."
        actions={<button>Go</button>}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Players" })).toBeInTheDocument();
    expect(screen.getByText("Every player.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Go" })).toBeInTheDocument();
  });

  it("SectionHeader is an h2 by default and an h3 on request", () => {
    const { rerender } = render(<SectionHeader id="s" title="Latest" />);
    expect(screen.getByRole("heading", { level: 2, name: "Latest" })).toHaveAttribute("id", "s");
    rerender(<SectionHeader title="Latest" as="h3" />);
    expect(screen.getByRole("heading", { level: 3, name: "Latest" })).toBeInTheDocument();
  });

  it("StatTile shows its label, value and hint", () => {
    render(<StatTile label="Matches" value="1,243" hint="2008 to 2026" tone="primary" />);
    expect(screen.getByText("Matches")).toBeInTheDocument();
    expect(screen.getByText("1,243")).toHaveClass("text-primary");
    expect(screen.getByText("2008 to 2026")).toBeInTheDocument();
  });

  it("Skeleton is hidden from assistive technology", () => {
    const { container } = render(<Skeleton className="h-8" />);
    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });

  it("EmptyState explains what is missing", () => {
    render(<EmptyState icon={Inbox} title="No matches" description="Try another season." />);
    expect(screen.getByText("No matches")).toBeInTheDocument();
    expect(screen.getByText("Try another season.")).toBeInTheDocument();
  });
});
