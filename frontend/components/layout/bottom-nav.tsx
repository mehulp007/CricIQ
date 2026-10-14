"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useCompetition } from "@/components/competition/use-competition";
import { SidebarContent } from "@/components/layout/sidebar";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { BOTTOM_NAV_PATHS, PRIMARY_NAV, isActive, navHref } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const ITEMS = PRIMARY_NAV.filter((item) => BOTTOM_NAV_PATHS.includes(item.path));
const tab =
  "flex flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors";

/** On phones: the four most-used pages one tap away, and everything else under "More". */
export function BottomNav() {
  const pathname = usePathname();
  const competition = useCompetition();
  const [open, setOpen] = useState(false);

  return (
    <nav
      aria-label="Quick"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
    >
      <ul className="flex h-16">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(item, pathname, competition);
          return (
            <li key={item.label} className="flex flex-1">
              <Link
                href={navHref(item, competition)}
                aria-current={active ? "page" : undefined}
                className={cn(tab, active ? "text-primary" : "text-muted-foreground")}
              >
                <Icon className="size-5" aria-hidden="true" />
                {item.label}
              </Link>
            </li>
          );
        })}
        <li className="flex flex-1">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <button
                type="button"
                aria-label="Open navigation"
                className={cn(tab, "text-muted-foreground")}
              >
                <Menu className="size-5" aria-hidden="true" />
                More
              </button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 bg-sidebar p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <SidebarContent onNavigate={() => setOpen(false)} />
            </SheetContent>
          </Sheet>
        </li>
      </ul>
    </nav>
  );
}
