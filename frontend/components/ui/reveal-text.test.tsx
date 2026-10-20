import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Bowled } from "@/components/layout/bowled";
import { PageHeader } from "@/components/ui/page-header";
import { RevealText } from "@/components/ui/reveal-text";
import { SectionHeader } from "@/components/ui/section-header";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RevealText", () => {
  it("splits plain text into words that keep the heading's name and spaces", () => {
    render(<PageHeader title="Match Explorer for every season" />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveAccessibleName("Match Explorer for every season");
    expect(heading.querySelectorAll("[data-stagger] > span")).toHaveLength(5);
  });

  it("fades other content in whole", () => {
    render(
      <SectionHeader
        title={
          <>
            IPL <em>2026</em>
          </>
        }
      />,
    );
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent("IPL 2026");
    expect(heading.querySelector("[data-fade]")).not.toBeNull();
  });

  it("starts hidden, word by word, when rendered in the browser", () => {
    const { container } = render(<RevealText>Every ball matters</RevealText>);
    expect(container.firstElementChild).toHaveAttribute("data-reveal", "hidden");
  });
});

describe("Bowled", () => {
  it("draws its scene on a described canvas, with a way to see it again", () => {
    render(<Bowled />);
    expect(screen.getByRole("img", { name: /bails fly off/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bowl it again" })).toBeInTheDocument();
  });

  it("leaves the words alone with reduced motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("reduce"),
      addEventListener() {},
      removeEventListener() {},
    }));
    const { container } = render(<Bowled />);
    expect(container).toBeEmptyDOMElement();
  });
});
