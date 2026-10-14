"use client";

import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { useCompetition } from "@/components/competition/use-competition";
import { NavList } from "@/components/layout/nav-list";
import { Separator } from "@/components/ui/separator";
import { competitionPath, getCompetition } from "@/lib/competitions";

/** Which competition the pages below belong to; switch it from the top bar. */
function CompetitionContext({ onNavigate }: { onNavigate?: () => void }) {
  const competition = getCompetition(useCompetition());
  return (
    <Link
      href={competitionPath(competition.id)}
      onClick={onNavigate}
      aria-label={`Current competition: ${competition.label}, ${competition.name}`}
      className="mx-1 flex flex-col gap-0.5 rounded-xl border border-sidebar-border bg-sidebar-accent/40 px-3 py-2.5 transition-colors hover:bg-sidebar-accent"
    >
      <span className="flex items-baseline gap-2">
        <span className="font-mono text-sm font-semibold text-sidebar-primary">
          {competition.label}
        </span>
        <span className="text-[11px] text-muted-foreground">{competition.format}</span>
      </span>
      <span className="truncate text-xs text-sidebar-foreground/80">{competition.name}</span>
    </Link>
  );
}

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto px-3 py-5">
      <Link href="/" onClick={onNavigate} className="px-3" aria-label="CricIQ home">
        <Logo />
      </Link>
      <CompetitionContext onNavigate={onNavigate} />
      <nav aria-label="Primary" className="flex-1">
        <NavList group="primary" onNavigate={onNavigate} />
      </nav>
      <div className="flex flex-col gap-3">
        <Separator />
        <nav aria-label="Secondary">
          <NavList group="secondary" onNavigate={onNavigate} />
        </nav>
        <p className="px-3 text-xs leading-relaxed text-muted-foreground">
          Data: Cricsheet (ODC-BY). Not affiliated with any league, board or the ICC.
        </p>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 border-r border-sidebar-border bg-sidebar lg:block">
      <SidebarContent />
    </aside>
  );
}
