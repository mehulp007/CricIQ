import { describe, expect, it } from "vitest";

import { fitText, formatFigure, linear, niceTicks, textWidth } from "@/lib/chart-scale";

describe("chart scales", () => {
  it("ticks are round numbers from zero past the maximum", () => {
    expect(niceTicks(0, 47)).toEqual([0, 10, 20, 30, 40, 50]);
    expect(niceTicks(0, 1.7, 4)).toEqual([0, 0.5, 1, 1.5, 2]);
    expect(niceTicks(0, 15109, 4)).toEqual([0, 5000, 10000, 15000, 20000]);
  });

  it("ticks reach below zero for negative values", () => {
    const ticks = niceTicks(-12, 30);
    expect(ticks[0]).toBeLessThanOrEqual(-12);
    expect(ticks).toContain(0);
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(30);
  });

  it("a flat domain gives one tick and maps to the range start", () => {
    expect(niceTicks(0, 0)).toEqual([0]);
    expect(linear([5, 5], [10, 90])(5)).toBe(10);
  });

  it("maps linearly, including reversed ranges", () => {
    const y = linear([0, 100], [400, 0]);
    expect(y(0)).toBe(400);
    expect(y(25)).toBe(300);
    expect(y(100)).toBe(0);
  });

  it("formats figures with grouping and no trailing zeros", () => {
    expect(formatFigure(15109)).toBe("15,109");
    expect(formatFigure(58.776)).toBe("58.78");
    expect(formatFigure(7.5, 1)).toBe("7.5");
    expect(formatFigure(null)).toBe("—");
    expect(formatFigure(Number.NaN)).toBe("—");
  });

  it("fits text into a width", () => {
    expect(fitText("Kohli", 1000, 16)).toBe("Kohli");
    const cut = fitText("Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium", 200, 16);
    expect(cut.endsWith("…")).toBe(true);
    expect(textWidth(cut, 16)).toBeLessThanOrEqual(200 + 16);
  });
});
