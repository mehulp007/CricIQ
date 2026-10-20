"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

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

/**
 * The pill behind the current page, glowing on its edge. One element per list: it slides (a CSS
 * transform on a springy curve, app/globals.css) to the item under the pointer or with keyboard
 * focus, and back again. `NavList` places it.
 */
const PILL =
  "nav-pill pointer-events-none absolute inset-x-0 top-0 -z-10 rounded-lg bg-sidebar-accent/60 data-[current]:bg-sidebar-accent data-[current]:shadow-[inset_2px_0_0_var(--sidebar-primary),0_0_18px_-6px_var(--sidebar-primary)]";

function Item({
  item,
  active,
  href,
  onNavigate,
  onPoint,
}: {
  item: NavItem;
  active: boolean;
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
        data-nav-item={item.label}
        className={cn(
          itemClass,
          active
            ? "text-sidebar-accent-foreground"
            : "text-sidebar-foreground/75 hover:text-sidebar-accent-foreground",
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
  const listRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLSpanElement>(null);
  const [pointed, setPointed] = useState<string | null>(null);
  const items = NAV_GROUPS[group].filter((item) => isShown(item, competition));
  const current = items.find((item) => isActive(item, pathname, competition))?.label ?? null;
  const pillAt = pointed ?? current;

  // Move the pill onto its item (measured, so it follows whatever the sidebar's layout is). After
  // paint: measuring during hydration would hold up the page's first frame for a highlight.
  useEffect(() => {
    const list = listRef.current;
    const pill = pillRef.current;
    if (!list || !pill) return;
    const target = pillAt
      ? list.querySelector<HTMLElement>(`[data-nav-item="${CSS.escape(pillAt)}"]`)
      : null;
    if (!target) {
      pill.dataset.hidden = "";
      return;
    }
    const top = target.getBoundingClientRect().top - list.getBoundingClientRect().top;
    // The first placement doesn't slide in from the top of the list.
    if (pill.dataset.placed === undefined) pill.style.transition = "none";
    pill.style.transform = `translateY(${top}px)`;
    pill.style.height = `${target.offsetHeight}px`;
    pill.dataset.placed = "";
    delete pill.dataset.hidden;
    if (pillAt === current) pill.dataset.current = "";
    else delete pill.dataset.current;
    if (pill.style.transition === "none") {
      void pill.offsetHeight;
      pill.style.transition = "";
    }
  }, [pillAt, current]);
  const render = (list: readonly NavItem[]) =>
    list.map((item) => (
      <Item
        key={item.label}
        item={item}
        href={navHref(item, competition)}
        active={item.label === current}
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
      <ul className="flex flex-col gap-0.5">{render(items)}</ul>
    ) : (
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
  return (
    // Each list (the sidebar, the phone menu) has its own pill.
    <div ref={listRef} className="relative isolate" {...leave}>
      <span ref={pillRef} aria-hidden="true" data-hidden="" className={PILL} />
      {list}
    </div>
  );
}
