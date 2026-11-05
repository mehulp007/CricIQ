import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  BarChart,
  ColumnChart,
  GroupedBars,
  HeadlineNumber,
  LineChart,
  SmallMultiples,
  TableCard,
} from "@/components/charts/svg/charts";
import { ChartFrame } from "@/components/charts/svg/frame";
import { CHART_SIZES, CHART_THEMES, chartTheme } from "@/components/charts/svg/theme";

const size = CHART_SIZES.landscape;
const theme = CHART_THEMES.dark;

function frame(children: Parameters<typeof ChartFrame>[0]["children"], title = "Runs by format") {
  return render(
    <ChartFrame
      width={size.width}
      height={size.height}
      theme={theme}
      title={title}
      subtitle="Men's ODIs, Tests and T20Is"
      footer="Data: Cricsheet (ODC-BY 1.0)"
      description="Bars of runs by format"
    >
      {children}
    </ChartFrame>,
  );
}

const ROWS = [
  { label: "ODI", value: 15109 },
  { label: "Test", value: 9230 },
  { label: "T20I", value: 4188, display: "4,188*" },
];

describe("exportable charts", () => {
  it("the frame is a labelled image with its export size, title and data line", () => {
    frame(() => null);
    const svg = screen.getByRole("img", { name: /Runs by format/ });
    expect(svg).toHaveAttribute("viewBox", "0 0 1200 675");
    expect(svg.dataset.exportWidth).toBe("1200");
    expect(svg).toHaveTextContent("CricIQ");
    expect(svg).toHaveTextContent("Data: Cricsheet (ODC-BY 1.0)");
  });

  it("bars write every figure, as given or formatted", () => {
    const { container } = frame((plot) => (
      <BarChart plot={plot} theme={theme} frame={size} rows={ROWS} />
    ));
    expect(container).toHaveTextContent("15,109");
    expect(container).toHaveTextContent("4,188*");
    expect(container.querySelectorAll("rect")).toHaveLength(1 + ROWS.length);
  });

  it("bars cope with one row, fifty rows, missing and negative values", () => {
    const many = Array.from({ length: 50 }, (_, i) => ({ label: `P${i}`, value: i - 10 }));
    const { container } = frame((plot) => (
      <BarChart
        plot={plot}
        theme={theme}
        frame={size}
        rows={[{ label: "none", value: null }, ...many]}
      />
    ));
    expect(container).toHaveTextContent("—");
    for (const rect of Array.from(container.querySelectorAll("rect"))) {
      expect(Number(rect.getAttribute("width"))).toBeGreaterThanOrEqual(0);
      expect(Number.isNaN(Number(rect.getAttribute("y")))).toBe(false);
    }
  });

  it("columns draw a line on its own scale with a legend", () => {
    const rows = Array.from({ length: 20 }, (_, i) => ({
      label: String(i + 1),
      value: 7 + (i % 5),
    }));
    const { container } = frame((plot) => (
      <ColumnChart
        plot={plot}
        theme={theme}
        frame={size}
        rows={rows}
        labelEvery={5}
        line={{ label: "Wickets per over", values: rows.map((_, i) => i / 20) }}
      />
    ));
    expect(container).toHaveTextContent("Wickets per over");
    expect(container.querySelector("polyline")).not.toBeNull();
  });

  it("grouped bars give each measure a legend key and every bar a figure", () => {
    const { container } = frame((plot) => (
      <GroupedBars
        plot={plot}
        theme={theme}
        frame={size}
        series={["Runs", "Average"]}
        rows={[
          { label: "ODI", values: [15109, 58.78] },
          { label: "Test", values: [9230, null] },
        ]}
      />
    ));
    expect(container).toHaveTextContent("Runs");
    expect(container).toHaveTextContent("58.78");
    expect(container).toHaveTextContent("—");
  });

  it("lines handle a single season", () => {
    const { container } = frame((plot) => (
      <LineChart
        plot={plot}
        theme={theme}
        frame={size}
        labels={["2024"]}
        series={[{ name: "Runs", values: [741] }]}
      />
    ));
    expect(container.querySelectorAll("circle")).toHaveLength(1);
    expect(container).toHaveTextContent("741");
  });

  it("small multiples, headline numbers and table cards render their content", () => {
    const { container } = frame((plot) => (
      <>
        <SmallMultiples
          plot={plot}
          theme={theme}
          frame={size}
          panels={[
            { title: "Runs", rows: ROWS },
            { title: "Average", rows: [{ label: "ODI", value: 58.78 }] },
          ]}
        />
        <HeadlineNumber
          plot={plot}
          theme={theme}
          frame={size}
          items={[{ label: "Runs", value: "75*" }]}
        />
        <TableCard
          plot={plot}
          theme={theme}
          frame={size}
          columns={[{ header: "Player" }, { header: "Runs", numeric: true }]}
          rows={[["Kohli", "75*"]]}
        />
      </>
    ));
    expect(container).toHaveTextContent("AVERAGE");
    expect(container).toHaveTextContent("75*");
    expect(container).toHaveTextContent("Kohli");
  });

  it("a chosen accent becomes the first series colour", () => {
    expect(chartTheme("paper", "#ff0000").series[0]).toBe("#ff0000");
    expect(chartTheme("paper").series[0]).toBe(CHART_THEMES.paper.series[0]);
  });
});
