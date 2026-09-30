export type MilestoneStatus = "done" | "active" | "planned";

export interface Milestone {
  id: string;
  title: string;
  summary: string;
  status: MilestoneStatus;
}

/** Build roadmap shown on the Overview page; source of truth is docs/PLAN.md §16. */
export const ROADMAP: readonly Milestone[] = [
  {
    id: "M0",
    title: "Foundations",
    summary: "Monorepo, tooling, CI, design system and application shell.",
    status: "done",
  },
  {
    id: "M1",
    title: "Data warehouse",
    summary: "Every IPL ball since 2008 from Cricsheet, normalized, validated and versioned.",
    status: "done",
  },
  {
    id: "M2",
    title: "Match explorer & replay",
    summary: "Browse any IPL match and replay it ball by ball as if it were live.",
    status: "active",
  },
  {
    id: "M3",
    title: "Win probability",
    summary: "Calibrated, explainable win probability updated after every delivery.",
    status: "planned",
  },
  {
    id: "M4",
    title: "Score projection",
    summary: "Projected totals with honest uncertainty ranges and threshold odds.",
    status: "planned",
  },
  {
    id: "M5",
    title: "Player lab",
    summary: "Contextual batting and bowling profiles with phase and situation splits.",
    status: "planned",
  },
  {
    id: "M6",
    title: "Matchup lab",
    summary: "Batter vs bowler analysis with sample-size-aware estimates.",
    status: "planned",
  },
];
