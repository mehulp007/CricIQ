import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CountUp } from "@/components/ui/count-up";
import { StaggerGrid } from "@/components/ui/stagger-grid";

/** jsdom has no layout: put every element on screen (or off it) and drive the frames by hand. */
function stage(onScreen: boolean) {
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
    top: onScreen ? 10 : 5000,
    bottom: onScreen ? 50 : 5040,
  } as DOMRect);
  const observers: ((entries: { isIntersecting: boolean }[]) => void)[] = [];
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
        observers.push(callback);
      }
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  let now = 0;
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => frames.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.spyOn(performance, "now").mockImplementation(() => now);
  return {
    arrive: () => observers.forEach((cb) => cb([{ isIntersecting: true }])),
    advance(ms: number) {
      now += ms;
      frames.splice(0).forEach((cb) => cb(now));
    },
  };
}

/** Render on the "server", then hydrate that HTML, as on the first page of a visit. */
function hydrate(ui: ReactElement) {
  const container = document.createElement("div");
  container.innerHTML = renderToString(ui);
  document.body.appendChild(container);
  return render(ui, { container, hydrate: true });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("CountUp", () => {
  it("leaves a number the visitor already sees as it is", () => {
    const { advance } = stage(true);
    hydrate(<CountUp value={1243} text="1,243" />);
    advance(100);
    expect(screen.getByText("1,243")).toBeInTheDocument();
  });

  it("counts up from zero as it scrolls into view, ending on its exact text", () => {
    const { arrive, advance } = stage(false);
    const { container } = hydrate(<CountUp value={100000} text="1,00,000" />);
    expect(container).toHaveTextContent("1,00,000");
    arrive();
    expect(container).toHaveTextContent(/^0$/);
    advance(300);
    const midway = Number(container.textContent!.replace(/,/g, ""));
    expect(midway).toBeGreaterThan(0);
    expect(midway).toBeLessThan(100000);
    advance(2000);
    expect(container).toHaveTextContent(/^1,00,000$/);
  });

  it("counts from the start when rendered in the browser", () => {
    const { advance } = stage(true);
    const { container } = render(<CountUp value={54.5} text="+54.5%" />);
    advance(16);
    expect(container.textContent).toMatch(/^\+\d+\.\d%$/);
    advance(2000);
    expect(container).toHaveTextContent(/^\+54\.5%$/);
  });
});

describe("StaggerGrid", () => {
  const grid = (
    <StaggerGrid as="ul">
      <li>One</li>
      <li>Two</li>
    </StaggerGrid>
  );

  it("numbers its items, and hides hydrated ones only below the fold", () => {
    stage(false);
    const { container } = hydrate(grid);
    const list = container.querySelector("ul")!;
    expect(list).toHaveAttribute("data-reveal", "hidden");
    expect(list.children[1]).toHaveStyle({ "--i": "1" });
  });

  it("leaves a hydrated grid on screen as it is", () => {
    stage(true);
    const { container } = hydrate(grid);
    expect(container.querySelector("ul")).not.toHaveAttribute("data-reveal");
  });

  it("starts hidden when rendered in the browser", () => {
    stage(true);
    const { container } = render(grid);
    expect(container.querySelector("ul")).toHaveAttribute("data-reveal", "hidden");
  });
});
