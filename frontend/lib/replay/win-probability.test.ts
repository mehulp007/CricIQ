import { describe, expect, it } from "vitest";

import final2019 from "@/data/featured/1181768.json";
import doubleSuperOver from "@/data/featured/1216517.json";
import type { Timeline } from "@/lib/api/types";

import {
  describeFactor,
  explanationAt,
  formatPercent,
  matchOvers,
  recentForm,
  swingAt,
  turningPoints,
  wpAt,
  wpBefore,
  wpSeries,
} from "./win-probability";

const final = final2019 as unknown as Timeline;
const superOvers = doubleSuperOver as unknown as Timeline;
const last = final.deliveries.length - 1;

describe("wpAt", () => {
  it("starts from the pre-match estimate and ends on the result", () => {
    const start = wpAt(final, -1)!;
    expect(start).toBeGreaterThan(0.2);
    expect(start).toBeLessThan(0.8);
    // Mumbai batted first and won by one run.
    expect(wpAt(final, last)).toBe(1);
  });

  it("holds the regulation estimate through unmodelled super overs", () => {
    const regulationEnd = superOvers.deliveries.findLastIndex((d) => d.innings_no === 2);
    expect(wpAt(superOvers, regulationEnd)).toBe(0.5);
    expect(wpAt(superOvers, superOvers.deliveries.length - 1)).toBe(0.5);
  });
});

describe("swings", () => {
  it("measures each ball against the state before it", () => {
    expect(wpBefore(final, 0)).toBe(final.innings[0].wp_start);
    const chaseStart = final.deliveries.findIndex((d) => d.innings_no === 2);
    expect(wpBefore(final, chaseStart)).toBe(final.innings[1].wp_start);
    expect(swingAt(final, 1)).toBeCloseTo(final.deliveries[1].wp! - final.deliveries[0].wp!);
  });

  it("finds the last-ball wicket as the decisive turning point", () => {
    const points = turningPoints(final, 3);
    expect(points).toHaveLength(3);
    expect(points[0].index).toBe(last);
    expect(points[0].side).toBe("a");
    expect(Math.abs(points[0].swing)).toBeGreaterThanOrEqual(Math.abs(points[1].swing));
    // No spoilers: only swings that have already happened.
    expect(turningPoints(final, 5, 40).every((p) => p.index <= 40)).toBe(true);
  });

  it("builds a series on one axis with the chase starting at 20 overs", () => {
    const series = wpSeries(final, last);
    expect(series[0]).toMatchObject({ x: 0, index: -1 });
    expect(series.some((p) => p.x === 20 && p.index === -1)).toBe(true);
    expect(series.at(-1)).toMatchObject({ wp: 100, index: last });
    expect(series.every((p) => p.wp >= 0 && p.wp <= 100)).toBe(true);
    expect(wpSeries(final, 10).at(-1)?.index).toBe(10);
    expect(matchOvers({ innings_no: 2, legal_ball_no: 30 })).toBe(25);
  });
});

describe("explanations", () => {
  it("explains the batting side's chance, largest factor first", () => {
    const at = 60;
    const explanation = explanationAt(final, at)!;
    expect(explanation.battingSide).toBe("a");
    expect(explanation.factors.map((f) => f.key).sort()).toEqual([
      "recent",
      "situation",
      "wickets",
    ]);
    const sizes = explanation.factors.map((f) => Math.abs(f.points));
    expect(sizes).toEqual([...sizes].sort((x, y) => y - x));
    // Points add up to the gap between this estimate and the model's average.
    const total = explanation.factors.reduce((sum, f) => sum + f.points, 0);
    expect(total / 100).toBeCloseTo(final.deliveries[at].wp! - explanation.base, 1);
  });

  it("has nothing to explain once the result is certain", () => {
    expect(explanationAt(final, last)).toBeNull();
  });

  it("describes factors in cricket language", () => {
    const chaseBall = final.deliveries.findIndex((d) => d.innings_no === 2) + 30;
    expect(describeFactor(final, chaseBall, "situation").detail).toMatch(
      /^Need \d+ from \d+ balls$/,
    );
    expect(describeFactor(final, chaseBall, "wickets").label).toBe("Wickets in hand");
    expect(describeFactor(final, -1, "situation").detail).toBe("Before the first ball");
    const form = recentForm(final, chaseBall);
    expect(form.runs).toBeGreaterThanOrEqual(0);
    expect(form.wickets).toBeLessThanOrEqual(12);
  });
});

describe("formatPercent", () => {
  it("rounds sensibly at the extremes", () => {
    expect(formatPercent(0.624)).toBe("62%");
    expect(formatPercent(0.004)).toBe("<1%");
    expect(formatPercent(0.996)).toBe(">99%");
    expect(formatPercent(1)).toBe("100%");
  });
});
