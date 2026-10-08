import {
  BookOpen,
  BrainCircuit,
  Calculator,
  CalendarRange,
  Dices,
  FlaskConical,
  GitCompareArrows,
  Info,
  LayoutDashboard,
  Shield,
  Swords,
  Users,
  type LucideIcon,
} from "lucide-react";

import { competitionPath, getCompetition, isTest, type CompetitionId } from "@/lib/competitions";

export type MilestoneId =
  "M0" | "M2" | "M3" | "M5" | "M6" | "V1-a" | "V1-b" | "V1-c" | "V1-d" | "v1.0";

export interface NavItem {
  /** Within the competition being browsed ("/matches" is /ipl/matches), or a global page. */
  path: string;
  scope: "competition" | "global";
  label: string;
  icon: LucideIcon;
  /** Milestone in docs/PLAN.md §16 that ships this page. */
  milestone: MilestoneId;
  /** Only shown where the competition has this content (the Analytics Lab; the
   * simulator in limited-overs cricket, the chase calculator in Tests). */
  requires?: "lab" | "limited" | "test";
}

/**
 * Milestones already shipped. Pages from later milestones are listed in the
 * sidebar as "coming soon" so the product shape is visible from day one, but
 * are never linked to placeholder content.
 */
export const SHIPPED_MILESTONES: ReadonlySet<MilestoneId> = new Set([
  "M0",
  "M2",
  "M3",
  "M5",
  "M6",
  "V1-a",
  "V1-b",
  "V1-c",
  "V1-d",
  "v1.0",
]);

const page = (path: string, label: string, icon: LucideIcon, milestone: MilestoneId) =>
  ({ path, scope: "competition", label, icon, milestone }) as const;

export const PRIMARY_NAV: readonly NavItem[] = [
  page("", "Overview", LayoutDashboard, "M0"),
  page("/matches", "Matches", CalendarRange, "M2"),
  page("/players", "Players", Users, "M5"),
  page("/matchups", "Matchups", Swords, "M6"),
  page("/compare", "Compare", GitCompareArrows, "V1-a"),
  page("/teams", "Teams", Shield, "V1-c"),
  { ...page("/simulator", "Simulator", Dices, "V1-d"), requires: "limited" },
  { ...page("/chase", "Chase calculator", Calculator, "V1-d"), requires: "test" },
  { ...page("/lab", "Analytics Lab", FlaskConical, "V1-b"), requires: "lab" },
  page("/models", "Model Insights", BrainCircuit, "M3"),
];

export const SECONDARY_NAV: readonly NavItem[] = [
  { path: "/writeup", scope: "global", label: "The write-up", icon: BookOpen, milestone: "v1.0" },
  { path: "/about", scope: "global", label: "About & Methodology", icon: Info, milestone: "M0" },
];

export function isAvailable(item: NavItem): boolean {
  return SHIPPED_MILESTONES.has(item.milestone);
}

/** Whether the competition has the item's page (the Analytics Lab covers the IPL so far;
 * Tests have a chase calculator instead of a match simulator). */
export function isShown(item: NavItem, competition: CompetitionId): boolean {
  switch (item.requires) {
    case "lab":
      return getCompetition(competition).lab;
    case "limited":
      return !isTest(competition);
    case "test":
      return isTest(competition);
    default:
      return true;
  }
}

export function navHref(item: NavItem, competition: CompetitionId): string {
  return item.scope === "global" ? item.path : competitionPath(competition, item.path);
}

/** Active if the path is the item itself or nested below it (the overview only matches exactly). */
export function isActive(item: NavItem, pathname: string, competition: CompetitionId): boolean {
  const href = navHref(item, competition);
  if (item.scope === "competition" && item.path === "") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}
