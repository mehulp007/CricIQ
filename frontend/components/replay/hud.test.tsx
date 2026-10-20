import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BallChip } from "@/components/replay/ball-chip";
import { PressurePulse, pulseFor } from "@/components/replay/pressure-pulse";
import { FlipScore } from "@/components/replay/scoreboard-frame";
import { WinProbabilityBar } from "@/components/replay/win-probability-bar";
import { TooltipProvider } from "@/components/ui/tooltip";
import final2019 from "@/data/featured/ipl/1181768.json";
import type { Timeline } from "@/lib/api/types";

const timeline = final2019 as unknown as Timeline;
const ball = (pick: (d: Timeline["deliveries"][number]) => boolean) =>
  timeline.deliveries.find(pick)!;

describe("pressure pulse", () => {
  it("breathes slowly at rest and quickens above the 75th percentile", () => {
    expect(pulseFor(0).speed).toBe(4);
    expect(pulseFor(50).speed).toBeGreaterThan(pulseFor(75).speed);
    expect(pulseFor(75).speed).toBe(1.8);
    expect(pulseFor(100).speed).toBe(1.2);
    // Never faster than about a beat a second, and brighter with pressure.
    expect(pulseFor(250).speed).toBe(1.2);
    expect(pulseFor(100).intensity).toBeGreaterThan(pulseFor(10).intensity);
  });

  it("is decorative, and absent once there is no next ball", () => {
    const { container, rerender } = render(<PressurePulse pressure={92} />);
    const ring = container.querySelector(".pressure-pulse")!;
    expect(ring).toHaveAttribute("aria-hidden", "true");
    expect(ring).toHaveStyle({ "--pulse-speed": `${pulseFor(92).speed}s` });
    rerender(<PressurePulse pressure={null} />);
    expect(container.querySelector(".pressure-pulse")).toBeNull();
  });

  it("rings the win-probability bar", () => {
    const { container } = render(
      <TooltipProvider>
        <WinProbabilityBar timeline={timeline} wp={0.4} pressure={80} />
      </TooltipProvider>,
    );
    expect(screen.getByRole("img", { name: /Mumbai Indians 40%/ })).toBeInTheDocument();
    expect(container.querySelector(".pressure-pulse")).not.toBeNull();
  });
});

describe("FlipScore", () => {
  it("reads as the plain score, its flipping digits hidden", () => {
    const { container } = render(<FlipScore text="149/8" />);
    expect(screen.getByText("149/8")).toHaveClass("sr-only");
    expect(container.querySelector("[aria-hidden=true]")).toHaveTextContent("149/8");
  });
});

describe("BallChip", () => {
  it("rings for a wicket, a six or a four, never for other balls", () => {
    const wicket = ball((d) => !!d.wicket?.is_dismissal);
    const six = ball((d) => d.is_six);
    const dot = ball((d) => d.runs_total === 0 && !d.wicket);
    for (const d of [wicket, six]) {
      const { container, unmount } = render(<BallChip delivery={d} flash />);
      expect(container.querySelector("[data-flash]")).not.toBeNull();
      unmount();
    }
    const { container } = render(<BallChip delivery={dot} flash />);
    expect(container.querySelector("[data-flash]")).toBeNull();
    expect(container).toHaveTextContent("•");
  });
});
