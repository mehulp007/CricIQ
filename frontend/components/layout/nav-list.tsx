"use client";

import { LayoutGroup, LazyMotion, MotionConfig, m } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useState } from "react";

import { useCompetition } from "@/components/competition/use-competition";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { motionFeatures } from "@/lib/animation";
import {
  NAV_SECTIONS,
  PRIMARY_NAV,
  SECONDARY_NAV,
  isActive,
  isAvailable,
  isShown,
  navHref,
  type NavItem,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";

const itemClass =
  "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors";

const NAV_GROUPS = { primary: PRIMARY_NAV, secondary: SECONDARY_NAV } as const;

/**
 * The pill behind the current page, glowing on its edge. It slides to the item under the pointer
 * (or with keyboard focus) and back again; `layoutId` makes Motion animate it between items.
 */
function Pill({ active }: { active: boolean }) {
  return (
    <m.span
      layoutId="nav-pill"
      aria-hidden="true"
      transition={{ type: "spring", stiffness: 500, damping: 40 }}
      className={cn(
        "absolute inset-0 -z-10 rounded-lg",
        active
          ? "bg-sidebar-accent shadow-[inset_2px_0_0_var(--sidebar-primary),0_0_18px_-6px_var(--sidebar-primary)]"
          : "bg-sidebar-accent/60",
      )}
    />
  );
}

function Item({
  item,
  active,
  pill,
  href,
  onNavigate,
  onPoint,
}: {
  item: NavItem;
  active: boolean;
  /** Whether the sliding pill sits on this item. */
  pill: boolean;
  href: string;
  onNavigate?: () => void;
  onPoint: (label: string) => void;
}) {
  const Icon = item.icon;
  if (!isAvailable(item)) {
    return (
      <li>
        <Tooltip>
          <TooltipTrigger asChild>
            {/* Not focusable: a focus-trapping drawer would otherwise auto-open the tooltip.
                The milestone is announced via sr-only text instead. */}
            <span
              aria-disabled="true"
              className={cn(itemClass, "cursor-default text-sidebar-foreground/40")}
            >
              <Icon className="size-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
              <Badge variant="outline" className="text-[10px] font-normal text-muted-foreground">
                Soon
              </Badge>
              <span className="sr-only">(ships in milestone {item.milestone})</span>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">Ships in milestone {item.milestone}</TooltipContent>
        </Tooltip>
      </li>
    );
  }
  return (
    <li>
      <Link
        href={href}
        onClick={onNavigate}
        onPointerEnter={() => onPoint(item.label)}
        onFocus={() => onPoint(item.label)}
        aria-current={active ? "page" : undefined}
        className={cn(
          itemClass,
          "isolate",
          active
            ? "text-sidebar-accent-foreground"
            : "text-sidebar-foreground/75 hover:text-sidebar-accent-foreground",
        )}
      >
        {pill && <Pill active={active} />}
        <Icon className={cn("size-4 shrink-0", active && "text-sidebar-primary")} />
        {item.label}
      </Link>
    </li>
  );
}

/**
 * Takes a group name rather than the items themselves: nav items carry icon
 * components, which cannot cross the server -> client component boundary.
 * The primary group is listed in its sections (Explore, Analyse).
 */
export function NavList({
  group,
  onNavigate,
}: {
  group: keyof typeof NAV_GROUPS;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const competition = useCompetition();
  // Each list (the sidebar, the phone menu) has its own pill.
  const layoutGroup = useId();
  const [pointed, setPointed] = useState<string | null>(null);
  const items = NAV_GROUPS[group].filter((item) => isShown(item, competition));
  const current = items.find((item) => isActive(item, pathname, competition))?.label ?? null;
  const pillAt = pointed ?? current;
  const render = (list: readonly NavItem[]) =>
    list.map((item) => (
      <Item
        key={item.label}
        item={item}
        href={navHref(item, competition)}
        active={item.label === current}
        pill={item.label === pillAt}
        onNavigate={onNavigate}
        onPoint={setPointed}
      />
    ));

  // Back to the current page when the pointer or focus leaves the list.
  const leave = {
    onPointerLeave: () => setPointed(null),
    onBlur: (event: React.FocusEvent<HTMLElement>) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setPointed(null);
    },
  };
  const list =
    group === "secondary" ? (
      <ul className="flex flex-col gap-0.5" {...leave}>
        {render(items)}
      </ul>
    ) : (
      <div className="flex flex-col gap-5" {...leave}>
        {NAV_SECTIONS.map((section) => (
          <div key={section} className="flex flex-col gap-1">
            <p className="px-3 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
              {section}
            </p>
            <ul className="flex flex-col gap-0.5">
              {render(items.filter((i) => i.section === section))}
            </ul>
          </div>
        ))}
      </div>
    );
  return (
    <LazyMotion features={motionFeatures} strict>
      <MotionConfig reducedMotion="user">
        <LayoutGroup id={layoutGroup}>{list}</LayoutGroup>
      </MotionConfig>
    </LazyMotion>
  );
}
