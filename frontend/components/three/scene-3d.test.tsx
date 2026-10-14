import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Scene3D } from "@/components/three/scene-3d";

// The scenes themselves (three.js) never load in these tests: a stand-in marks where one would.
vi.mock("next/dynamic", () => ({
  default: () =>
    function FakeScene() {
      return <div data-testid="scene-canvas" />;
    },
}));

function setup({ reducedMotion = false, webgl = true } = {}) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("reduce") ? reducedMotion : true,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    () => (webgl ? ({} as RenderingContext) : null) as never,
  );
}

function renderScene() {
  return render(
    <Scene3D
      scene="ball"
      poster="/3d/posters/cricket-ball.webp"
      width={640}
      height={640}
      label="A cricket ball, turning slowly"
    />,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Scene3D", () => {
  it("is one labelled image for screen readers, showing its poster", () => {
    setup();
    renderScene();
    const scene = screen.getByRole("img", { name: "A cricket ball, turning slowly" });
    expect(scene).toHaveAttribute("data-scene-state", "poster");
    expect(scene.querySelector("img")).toHaveAttribute("alt", "");
  });

  it("loads the scene after the visitor's first move, once the browser is idle", () => {
    setup();
    renderScene();
    act(() => vi.runAllTimers());
    // Nothing starts on its own: the page loads without the 3D's work.
    expect(screen.queryByTestId("scene-canvas")).toBeNull();
    fireEvent.pointerMove(window);
    expect(screen.queryByTestId("scene-canvas")).toBeNull();
    act(() => vi.runAllTimers());
    expect(screen.getByTestId("scene-canvas")).toBeInTheDocument();
  });

  it("starts on a key or a scroll as well", () => {
    setup();
    renderScene();
    fireEvent.keyDown(window, { key: "Tab" });
    act(() => vi.runAllTimers());
    expect(screen.getByTestId("scene-canvas")).toBeInTheDocument();
  });

  it("keeps the poster when motion should be reduced", () => {
    setup({ reducedMotion: true });
    renderScene();
    fireEvent.pointerMove(window);
    act(() => vi.runAllTimers());
    expect(screen.queryByTestId("scene-canvas")).toBeNull();
  });

  it("has a poster per theme, only the theme's own showing", () => {
    setup();
    render(
      <Scene3D
        scene="stadium"
        poster={{ dark: "/3d/posters/stadium-night.webp", light: "/3d/posters/stadium-day.webp" }}
        width={1200}
        height={900}
        label="A stadium"
      />,
    );
    const [night, day] = screen.getByRole("img", { name: "A stadium" }).querySelectorAll("img");
    expect(night.getAttribute("src")).toContain("stadium-night.webp");
    expect(night).toHaveClass("hidden", "dark:block");
    expect(day.getAttribute("src")).toContain("stadium-day.webp");
    expect(day).toHaveClass("dark:hidden");
    // Neither is fetched before it shows.
    expect(night).toHaveAttribute("loading", "lazy");
    expect(day).toHaveAttribute("loading", "lazy");
  });

  it("keeps the poster without WebGL", () => {
    setup({ webgl: false });
    renderScene();
    fireEvent.pointerMove(window);
    act(() => vi.runAllTimers());
    expect(screen.queryByTestId("scene-canvas")).toBeNull();
  });
});
