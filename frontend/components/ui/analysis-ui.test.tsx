import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CoverageNote, coverageText } from "@/components/ui/coverage-note";
import { withParam } from "@/lib/url";
import { RankedTable, rankLabel } from "@/components/ui/ranked-table";

describe("analysis page pieces", () => {
  it("filter params are set, cleared and reset the page", () => {
    const params = new URLSearchParams("team=MI&page=3");
    expect(withParam(params, "venue", "wankhede").toString()).toBe("team=MI&venue=wankhede");
    expect(withParam(params, "team", "all").toString()).toBe("");
    expect(withParam(params, "team", null).toString()).toBe("");
  });

  it("coverage reads as seasons and matches", () => {
    expect(
      coverageText("IPL", { first_season_label: "2008", last_season_label: "2026", matches: 1243 }),
    ).toBe("IPL 2008–2026, 1,243 matches");
    expect(
      coverageText("SA20", { first_season_label: "2023", last_season_label: "2023", matches: 1 }),
    ).toBe("SA20 2023, 1 match");
    expect(coverageText("BBL", { first_season_label: null, last_season_label: null, matches: 0 })).toBe(
      "BBL: 0 matches",
    );
    render(
      <CoverageNote
        competition="Tests"
        coverage={{ first_season_label: "2001", last_season_label: "2026", matches: 895 }}
      />,
    );
    expect(screen.getByText(/ball-by-ball data: Tests 2001–2026, 895 matches/)).toBeInTheDocument();
  });

  it("ranked tables print shared ranks with an equals sign", () => {
    expect(rankLabel(3, true)).toBe("=3");
    expect(rankLabel(4, false)).toBe("4");
    render(
      <RankedTable
        label="Highest partnerships"
        rowKey={(r) => r.name}
        rows={[
          { rank: 1, tied: false, name: "Gayle & Samuels", runs: 372 },
          { rank: 2, tied: true, name: "A & B", runs: 260 },
          { rank: 2, tied: true, name: "C & D", runs: 260 },
        ]}
        columns={[
          { key: "name", header: "Batters", cell: (r) => r.name },
          { key: "runs", header: "Runs", cell: (r) => r.runs, numeric: true },
        ]}
      />,
    );
    const table = screen.getByRole("table", { name: "Highest partnerships" });
    expect(within(table).getAllByText("=2")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "Highest partnerships" })).toHaveAttribute("tabindex", "0");
  });
});
