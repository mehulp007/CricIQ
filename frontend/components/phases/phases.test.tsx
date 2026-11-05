import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GroundsTable } from "@/components/phases/grounds-table";
import { PhaseCards } from "@/components/phases/phase-cards";
import { ResultsPanel } from "@/components/phases/results-panel";
import type { PhaseSummary, ResultSplit } from "@/lib/api/types";

const phase = (key: string, label: string, first: number, last: number | null): PhaseSummary => ({
  key,
  label,
  first_over: first,
  last_over: last,
  innings: 2480,
  runs: 120188,
  balls: 89153,
  wickets: 3575,
  fours: 14405,
  sixes: 3767,
  dots: 41266,
  run_rate: 8.09,
  runs_per_innings: 48.46,
  wickets_per_innings: 1.44,
  boundary_pct: 20.4,
  dot_pct: 46.3,
  balls_per_wicket: 24.94,
});

const PHASES = [
  phase("new_ball", "New ball", 1, 20),
  phase("middle", "Middle overs", 21, 80),
  phase("second_new_ball", "Second new ball", 81, null),
];

const side = (matches: number, won: number, drawn: number) => ({
  matches,
  won,
  drawn,
  win_pct: matches ? Math.round((1000 * won) / matches) / 10 : null,
});

describe("phase analysis pieces", () => {
  it("phase cards show the overs, innings and rates", () => {
    render(<PhaseCards phases={PHASES} />);
    const cards = screen.getByRole("list", { name: "Phases" });
    expect(within(cards).getAllByRole("listitem")).toHaveLength(3);
    expect(cards).toHaveTextContent("Overs 1–20 · 2,480 innings");
    expect(cards).toHaveTextContent("Overs 81 onwards");
    expect(cards).toHaveTextContent("8.09");
    expect(cards).toHaveTextContent("48.5");
    expect(cards).toHaveTextContent("3,767");
  });

  it("Test results count draws and leave out the total defended", () => {
    const results: ResultSplit = {
      matches: 899,
      batting_first: side(899, 404, 169),
      chasing: side(899, 326, 169),
      first_innings_average: 342.96,
      average_total_defended: null,
    };
    render(<ResultsPanel results={results} toss={[]} test team={null} />);
    expect(screen.getByText("Won batting second")).toBeInTheDocument();
    expect(screen.getAllByText(/169 drawn/)).toHaveLength(2);
    expect(screen.getByText("Runs in the match's first innings")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("a team's results and toss are its own", () => {
    const results: ResultSplit = {
      matches: 20,
      batting_first: side(9, 5, 0),
      chasing: side(11, 7, 0),
      first_innings_average: 171.4,
      average_total_defended: 185.2,
    };
    render(
      <ResultsPanel
        results={results}
        toss={[{ decision: "field", matches: 8, toss_winner_won: 5, win_pct: 62.5 }]}
        test={false}
        team="Mumbai Indians"
      />,
    );
    expect(screen.getByText("Mumbai Indians won chasing")).toBeInTheDocument();
    expect(screen.getByText("Average total defended 185.2")).toBeInTheDocument();
    const toss = screen.getByRole("table", { name: "When Mumbai Indians won the toss" });
    expect(within(toss).getByRole("row", { name: /Field/ })).toHaveTextContent("62.5%");
  });

  it("grounds list a run rate per phase, with a dash where none was bowled", () => {
    render(
      <GroundsTable
        phases={PHASES}
        grounds={[
          {
            venue_id: "lords",
            name: "Lord's",
            city: "London",
            matches: 30,
            phases: [
              { phase: "new_ball", balls: 6000, run_rate: 3.1 },
              { phase: "middle", balls: 12000, run_rate: 3.2 },
            ],
          },
        ]}
      />,
    );
    const row = screen.getByRole("row", { name: /Lord's/ });
    expect(row).toHaveTextContent("3.10");
    expect(row).toHaveTextContent("—");
    expect(screen.getByRole("columnheader", { name: "Second new ball RR" })).toBeInTheDocument();
  });
});
