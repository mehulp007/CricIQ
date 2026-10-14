"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCompetition } from "@/components/competition/use-competition";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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

function Item({
  item,
  active,
  href,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  href: string;
  onNavigate?: () => void;
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
        aria-current={active ? "page" : undefined}
        className={cn(
          itemClass,
          active
            ? "bg-sidebar-accent text-sidebar-accent-foreground before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-sidebar-primary"
            : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
        )}
      >
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
  const items = NAV_GROUPS[group].filter((item) => isShown(item, competition));
  const render = (list: readonly NavItem[]) =>
    list.map((item) => (
      <Item
        key={item.label}
        item={item}
        href={navHref(item, competition)}
        active={isActive(item, pathname, competition)}
        onNavigate={onNavigate}
      />
    ));

  if (group === "secondary") return <ul className="flex flex-col gap-0.5">{render(items)}</ul>;
  return (
    <div className="flex flex-col gap-5">
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
}
