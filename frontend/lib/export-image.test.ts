import { describe, expect, it } from "vitest";

import { csvCell, fileName, fontFamilies, resolveVariables, toCsv } from "@/lib/export-image";

describe("exporting charts", () => {
  it("names files from the chart title", () => {
    expect(fileName("Virat Kohli: runs by format", "png")).toBe("virat-kohli-runs-by-format.png");
    expect(fileName("Mumbaï / Wankhede — 2024!", "svg")).toBe("mumbai-wankhede-2024.svg");
    expect(fileName("***", "csv")).toBe("criciq-chart.csv");
  });

  it("quotes CSV cells only when needed", () => {
    expect(csvCell("Kohli")).toBe("Kohli");
    expect(csvCell("Kohli, V")).toBe('"Kohli, V"');
    expect(csvCell('the "king"')).toBe('"the ""king"""');
    expect(csvCell(null)).toBe("");
    expect(csvCell(58.78)).toBe("58.78");
  });

  it("never lets a cell run as a spreadsheet formula, but keeps negative numbers", () => {
    expect(csvCell("=HYPERLINK(1)")).toBe("'=HYPERLINK(1)");
    expect(csvCell("@cmd")).toBe("'@cmd");
    expect(csvCell("-12.5")).toBe("-12.5");
    expect(csvCell(-3)).toBe("-3");
  });

  it("writes rows with headers and CRLF line ends", () => {
    expect(
      toCsv(
        ["Player", "Runs"],
        [
          ["Kohli", 15109],
          ["Root, J", 7000],
        ],
      ),
    ).toBe('Player,Runs\r\nKohli,15109\r\n"Root, J",7000\r\n');
  });

  it("resolves CSS variables to their current values", () => {
    const values: Record<string, string> = {
      "--card": " #0b0f17 ",
      "--chart-1": "oklch(0.7 0.1 160)",
    };
    const out = resolveVariables(
      '<rect fill="var(--card)"/><rect fill="var(--chart-1)"/><rect fill="var(--missing)"/>',
      (name) => values[name] ?? "",
    );
    expect(out).toBe(
      '<rect fill="#0b0f17"/><rect fill="oklch(0.7 0.1 160)"/><rect fill="#888888"/>',
    );
  });

  it("reads the families in a font-family value", () => {
    expect(fontFamilies("'__Sora_abc', '__Sora_Fallback_abc', ui-sans-serif")).toEqual([
      "__Sora_abc",
      "__Sora_Fallback_abc",
      "ui-sans-serif",
    ]);
  });
});
