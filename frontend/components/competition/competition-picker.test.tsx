import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CompetitionPicker, type PickerCard } from "@/components/competition/competition-picker";

const IPL: PickerCard = {
  id: "ipl",
  href: "/ipl",
  label: "IPL",
  name: "Indian Premier League",
  format: "T20",
  span: "2008 to 2026",
  champion: "Royal Challengers Bengaluru",
  featured: "IPL 2026 final",
};
const TEST: PickerCard = {
  ...IPL,
  id: "test",
  href: "/test",
  label: "Test",
  name: "Men's Test cricket",
  format: "Test",
  span: "2001 to 2026",
  champion: null,
  featured: null,
};

function setup(reducedMotion = false) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("reduce") ? reducedMotion : false,
  }));
  render(
    <CompetitionPicker
      groups={[
        { title: "Leagues", cards: [IPL] },
        { title: "Internationals", cards: [TEST] },
      ]}
    />,
  );
  return screen.getByRole("link", { name: /^IPL\b/ });
}

function pointAt(card: HTMLElement, pointerType: string) {
  card.getBoundingClientRect = () => ({ left: 0, top: 0, width: 200, height: 100 }) as DOMRect;
  // The far right edge, a quarter of the way down.
  fireEvent.pointerMove(card, { clientX: 200, clientY: 25, pointerType });
}

beforeEach(() => {
  // jsdom's PointerEvent lacks pointerType: fall back to MouseEvent, which keeps the init.
  vi.stubGlobal(
    "PointerEvent",
    class extends MouseEvent {
      pointerType: string;
      constructor(type: string, init: PointerEventInit = {}) {
        super(type, init);
        this.pointerType = init.pointerType ?? "";
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CompetitionPicker", () => {
  it("lists each group's competitions as links with their details", () => {
    const ipl = setup();
    expect(screen.getByRole("heading", { name: "Leagues" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Internationals" })).toBeInTheDocument();
    expect(ipl).toHaveAccessibleName("IPL, Indian Premier League");
    expect(ipl).toHaveAttribute("href", "/ipl");
    // (jsdom runs the card's lines together without the spaces a browser puts between them.)
    expect(ipl).toHaveAccessibleDescription(
      /^T20 2008 to 2026\.\s*Royal Challengers Bengaluru, the latest champions\. Featured: IPL 2026 final$/,
    );
    const test = screen.getByRole("link", { name: "Test, Men's Test cricket" });
    expect(test).not.toHaveTextContent("champions");
  });

  it("leans a card towards the mouse and settles when it leaves", () => {
    const ipl = setup();
    pointAt(ipl, "mouse");
    expect(ipl.style.getPropertyValue("--ry")).toBe("4.50deg");
    expect(ipl.style.getPropertyValue("--rx")).toBe("1.75deg");
    expect(ipl.style.getPropertyValue("--gx")).toBe("100.0%");
    fireEvent.pointerLeave(ipl);
    expect(ipl.style.getPropertyValue("--ry")).toBe("");
  });

  it("stays flat for touch", () => {
    pointAt(setup(), "touch");
    expect(screen.getByRole("link", { name: /^IPL\b/ }).style.getPropertyValue("--ry")).toBe("");
  });

  it("stays flat when motion should be reduced", () => {
    const ipl = setup(true);
    pointAt(ipl, "mouse");
    expect(ipl.style.getPropertyValue("--ry")).toBe("");
  });
});
