"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCompetition } from "@/components/competition/use-competition";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  PRIMARY_NAV,
  SECONDARY_NAV,
  isActive,
  isAvailable,
  isShown,
  navHref,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";

const itemClass =
  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors";

const NAV_GROUPS = { primary: PRIMARY_NAV, secondary: SECONDARY_NAV } as const;

/**
 * Takes a group name rather than the items themselves: nav items carry icon
 * components, which cannot cross the server -> client component boundary.
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

  return (
    <ul className="flex flex-col gap-0.5">
      {items.map((item) => {
        const Icon = item.icon;

        if (!isAvailable(item)) {
          return (
            <li key={item.label}>
              <Tooltip>
                <TooltipTrigger asChild>
                  {/* Not focusable: a focus-trapping drawer would otherwise auto-open
                      the tooltip. The milestone is announced via sr-only text instead. */}
                  <span
                    aria-disabled="true"
                    className={cn(itemClass, "cursor-default text-sidebar-foreground/40")}
                  >
                    <Icon className="size-4 shrink-0" />
                    <span className="flex-1">{item.label}</span>
                    <Badge
                      variant="outline"
                      className="text-[10px] font-normal text-muted-foreground"
                    >
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

        const active = isActive(item, pathname, competition);
        return (
          <li key={item.label}>
            <Link
              href={navHref(item, competition)}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                itemClass,
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
              )}
            >
              <Icon className={cn("size-4 shrink-0", active && "text-sidebar-primary")} />
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
