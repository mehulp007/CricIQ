import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Counter } from "@/components/landing/counter";
import { HeroText } from "@/components/landing/hero-text";
import { ReducedMotionFallback } from "@/components/landing/reduced-motion-fallback";
import { landingFacts, probabilityRibbon } from "@/lib/landing";

describe("Counter", () => {
  it("renders the exact final value, for screen readers too", () => {
    const { container } = render(<Counter value={4_570_681} />);
    expect(container.querySelector("[data-counter]")).toHaveTextContent("4,570,681");
    expect(container.querySelector(".sr-only")).toHaveTextContent("4,570,681");
  });

  it("keeps decimals", () => {
    const { container } = render(<Counter value={0.5} decimals={1} />);
    expect(container.querySelector(".sr-only")).toHaveTextContent("0.5");
  });
});

describe("HeroText", () => {
  it("names the opening headline by its plain text, letters hidden", () => {
    render(<HeroText as="h1" intro lines={["Decode the game.", "Predict the next move."]} />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Decode the game. Predict the next move." }),
    ).toBeInTheDocument();
    expect(document.querySelectorAll(".landing-char").length).toBe(
      "Decodethegame.Predictthenextmove.".length,
    );
  });

  it("marks later headlines for splitting", () => {
    render(<HeroText id="x" lines={["Every outcome.", "Simulated."]} />);
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveAttribute("data-split");
    expect(heading).toHaveTextContent("Every outcome.Simulated.");
  });
});

describe("ReducedMotionFallback", () => {
  it("tells the four chapters with still figures", () => {
    render(<ReducedMotionFallback facts={landingFacts()} ribbon={probabilityRibbon()} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Decode the game\./);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(3);
    expect(screen.getAllByRole("img")).toHaveLength(4);
    expect(screen.getAllByText("4,570,681").length).toBeGreaterThan(0);
    expect(screen.getByText("Pollard's six")).toBeInTheDocument();
  });
});
