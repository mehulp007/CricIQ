import { act, render, screen } from "@testing-library/react";
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

  it("loads the scene once the browser is idle and the scene is on screen", () => {
    setup();
    renderScene();
    expect(screen.queryByTestId("scene-canvas")).toBeNull();
    act(() => vi.runAllTimers());
    expect(screen.getByTestId("scene-canvas")).toBeInTheDocument();
  });

  it("keeps the poster when motion should be reduced", () => {
    setup({ reducedMotion: true });
    renderScene();
    act(() => vi.runAllTimers());
    expect(screen.queryByTestId("scene-canvas")).toBeNull();
  });

  it("keeps the poster without WebGL", () => {
    setup({ webgl: false });
    renderScene();
    act(() => vi.runAllTimers());
    expect(screen.queryByTestId("scene-canvas")).toBeNull();
  });
});
