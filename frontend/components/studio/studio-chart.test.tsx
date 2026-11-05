import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MatchCard, matchRows, StudioChart } from "@/components/studio/studio-chart";
import type { MatchDetail, StudioResult } from "@/lib/api/types";
import { CHART_TYPES, DEFAULT_STYLE, type ChartType } from "@/lib/studio";

const columns = [
  { key: "runs", label: "Runs", kind: "count", descending: true },
  { key: "average", label: "Average", kind: "rate", descending: true },
  { key: "strike_rate", label: "Strike rate", kind: "rate", descending: true },
].map((c) => ({ ...c, kind: c.kind as "count", description: c.label, model: false }));

function result(count: number, split = false): StudioResult {
  const rows = Array.from({ length: count }, (_, i) => ({
    group: { key: `p${i}`, label: `Player ${i + 1}`, player_id: `p${i}`, color: null },
    rank: i + 1,
    tied: false,
    values: { runs: 1000 - i * 10, average: 40 - i * 0.2, strike_rate: 130 + i },
    display: {
      runs: String(1000 - i * 10),
      average: (40 - i * 0.2).toFixed(2),
      strike_rate: String(130 + i),
    },
    sample: 500,
  }));
  const series = split
    ? ["2023", "2024"].map((year) => ({
        group: { key: year, label: year, color: null, player_id: null },
        rank: null,
        tied: false,
        values: { runs: 500 },
        display: { runs: "500" },
        sample: 300,
      }))
    : [];
  return {
    coverage: {
      first_season: 2008,
      last_season: 2024,
      first_season_label: "2008",
      last_season_label: "2024",
      matches: 1000,
      first_date: "2008-04-18",
      last_date: "2024-05-26",
    },
    data_version: "v1",
    format: "T20",
    spec: {
      dataset: "batting",
      measures: columns.map((c) => c.key),
      group_by: "player",
      split_by: split ? "season" : null,
      filters: { players: [] },
      sort: "runs",
      order: "desc",
      min_sample: 0,
      limit: 50,
      series: 8,
    },
    dataset_label: "Batting innings",
    group_label: "Player",
    split_label: split ? "Season" : null,
    sample_label: "balls faced",
    columns,
    rows,
    series,
    cells: split
      ? rows.flatMap((r) =>
          ["2023", "2024"].map((year) => ({
            group: r.group.key,
            split: year,
            values: { runs: 250 },
            display: { runs: "250" },
            sample: 150,
          })),
        )
      : [],
    truncated: false,
    sql: "SELECT 1",
    params: [],
  };
}

function draw(data: StudioResult, chart: ChartType, labels = true) {
  return render(
    <StudioChart
      result={data}
      style={{ ...DEFAULT_STYLE, chart, labels }}
      title="Runs by player"
      subtitle="IPL"
      footer="Data: Cricsheet"
      image={null}
      svgRef={null}
    />,
  );
}

describe("StudioChart", () => {
  for (const { value: chart } of CHART_TYPES) {
    it(`draws ${chart} with one row and with fifty`, () => {
      for (const count of [1, 50]) {
        const { container, unmount } = draw(result(count), chart);
        const svg = container.querySelector("svg");
        expect(svg?.getAttribute("data-export-width")).toBe("1200");
        expect(container.textContent).toContain("Runs by player");
        if (chart !== "line" && chart !== "columns") {
          expect(container.textContent).toContain("1000");
          if (count > 1 && chart !== "headline") expect(container.textContent).toContain("990");
        }
        unmount();
      }
    });
  }

  it("draws a split as series", () => {
    const { container } = draw(result(3, true), "grouped");
    expect(container.textContent).toContain("2023");
    expect(container.textContent).toContain("250");
    const line = draw(result(3, true), "line");
    expect(line.container.querySelectorAll("polyline").length).toBeGreaterThan(0);
  });

  it("leaves the figures off when value labels are off", () => {
    const { container } = draw(result(5), "bars", false);
    expect(container.querySelectorAll("text").length).toBeLessThan(
      draw(result(5), "bars", true).container.querySelectorAll("text").length,
    );
  });

  it("shows a picture of your own in the corner", () => {
    const { container } = render(
      <StudioChart
        result={result(3)}
        style={DEFAULT_STYLE}
        title="Runs"
        subtitle=""
        footer="Data"
        image="data:image/png;base64,AAAA"
        svgRef={null}
      />,
    );
    const image = container.querySelector("image");
    expect(image?.getAttribute("href")).toBe("data:image/png;base64,AAAA");
    expect(image?.getAttribute("clip-path")).toMatch(/^url\(#chart-image-[\w-]+\)$/);
  });
});

const MATCH = {
  series: null,
  summary: {
    match_id: 1,
    date: "2024-05-26",
    result_text: "Kolkata Knight Riders won by 8 wickets",
    venue: { venue_id: "chepauk", name: "MA Chidambaram Stadium", city: "Chennai" },
    team_a: { name: "Sunrisers Hyderabad" },
    team_b: { name: "Kolkata Knight Riders" },
    player_of_match: ["MA Starc"],
  },
  innings: [
    {
      innings_no: 1,
      is_super_over: false,
      batting_team: { name: "Sunrisers Hyderabad" },
      runs: 113,
      wickets: 10,
      overs: "18.3",
      batting: [
        { name: "PJ Cummins", runs: 24, balls: 19, is_out: true },
        { name: "AK Markram", runs: 20, balls: 23, is_out: true },
      ],
      bowling: [
        { name: "AD Russell", wickets: 3, runs: 19 },
        { name: "MA Starc", wickets: 2, runs: 14 },
      ],
    },
    {
      innings_no: 2,
      is_super_over: false,
      batting_team: { name: "Kolkata Knight Riders" },
      runs: 114,
      wickets: 2,
      overs: "10.3",
      batting: [{ name: "VR Iyer", runs: 52, balls: 26, is_out: false }],
      bowling: [{ name: "PJ Cummins", wickets: 1, runs: 18 }],
    },
  ],
} as unknown as MatchDetail;

describe("MatchCard", () => {
  it("shows each innings with its best batter and bowler", () => {
    expect(matchRows(MATCH)).toEqual([
      ["Sunrisers Hyderabad", "113/10 (18.3)", "PJ Cummins 24 (19)", "AD Russell 3/19"],
      ["Kolkata Knight Riders", "114/2 (10.3)", "VR Iyer 52* (26)", "PJ Cummins 1/18"],
    ]);
    const { container } = render(
      <MatchCard
        match={MATCH}
        style={DEFAULT_STYLE}
        title="SRH v KKR"
        subtitle="Final"
        footer="Data"
        image={null}
        svgRef={null}
      />,
    );
    expect(container.textContent).toContain("VR Iyer 52* (26)");
  });
});
