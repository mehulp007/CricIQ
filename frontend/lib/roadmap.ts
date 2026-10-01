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
    status: "done",
  },
  {
    id: "M3",
    title: "Win probability",
    summary: "Calibrated, explainable win probability updated after every delivery.",
    status: "done",
  },
  {
    id: "M4",
    title: "Score projection",
    summary: "Projected totals with honest uncertainty ranges and threshold odds.",
    status: "done",
  },
  {
    id: "M5",
    title: "Player lab",
    summary: "Contextual batting and bowling profiles with phase and situation splits.",
    status: "done",
  },
  {
    id: "M6",
    title: "Matchup lab",
    summary: "Batter vs bowler analysis with sample-size-aware estimates.",
    status: "done",
  },
  {
    id: "v0.1",
    title: "MVP release",
    summary: "Polish, methodology, performance and accessibility audit across every page.",
    status: "done",
  },
  {
    id: "V1-a",
    title: "Compare, ratings and similar players",
    summary: "Side-by-side player comparison, transparent CricIQ Ratings and look-alike players.",
    status: "planned",
  },
  {
    id: "V1-b",
    title: "Momentum, pressure and the Analytics Lab",
    summary: "Leverage and momentum in every replay, each with a published validation.",
    status: "planned",
  },
  {
    id: "V1-c",
    title: "Team analytics",
    summary: "Team profiles and head-to-head records across seasons.",
    status: "planned",
  },
  {
    id: "V1-d",
    title: "Match simulator",
    summary: "Monte Carlo simulation of any fixture, plus a what-if sandbox in the replay.",
    status: "planned",
  },
];
