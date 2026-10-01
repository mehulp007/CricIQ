import {
  BrainCircuit,
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

export type MilestoneId = "M0" | "M2" | "M3" | "M5" | "M6" | "V1";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Milestone in docs/PLAN.md §16 that ships this page. */
  milestone: MilestoneId;
}

/**
 * Milestones already shipped. Pages from later milestones are listed in the
 * sidebar as "coming soon" so the product shape is visible from day one, but
 * are never linked to placeholder content.
 */
export const SHIPPED_MILESTONES: ReadonlySet<MilestoneId> = new Set(["M0", "M2", "M3", "M5"]);

export const PRIMARY_NAV: readonly NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard, milestone: "M0" },
  { href: "/matches", label: "Matches", icon: CalendarRange, milestone: "M2" },
  { href: "/players", label: "Players", icon: Users, milestone: "M5" },
  { href: "/matchups", label: "Matchups", icon: Swords, milestone: "M6" },
  { href: "/compare", label: "Compare", icon: GitCompareArrows, milestone: "V1" },
  { href: "/teams", label: "Teams", icon: Shield, milestone: "V1" },
  { href: "/simulator", label: "Simulator", icon: Dices, milestone: "V1" },
  { href: "/lab", label: "Analytics Lab", icon: FlaskConical, milestone: "V1" },
  { href: "/models", label: "Model Insights", icon: BrainCircuit, milestone: "M3" },
];

export const SECONDARY_NAV: readonly NavItem[] = [
  { href: "/about", label: "About & Methodology", icon: Info, milestone: "M0" },
];

export function isAvailable(item: NavItem): boolean {
  return SHIPPED_MILESTONES.has(item.milestone);
}

/** Active if the path is the item itself or nested below it ("/" only matches exactly). */
export function isActive(item: NavItem, pathname: string): boolean {
  if (item.href === "/") return pathname === "/";
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
