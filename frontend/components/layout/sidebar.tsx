import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { NavList } from "@/components/layout/nav-list";
import { Separator } from "@/components/ui/separator";

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-5">
      <Link href="/" onClick={onNavigate} className="px-3" aria-label="CricIQ home">
        <Logo />
      </Link>
      <nav aria-label="Primary" className="flex-1">
        <NavList group="primary" onNavigate={onNavigate} />
      </nav>
      <div className="flex flex-col gap-3">
        <Separator />
        <nav aria-label="Secondary">
          <NavList group="secondary" onNavigate={onNavigate} />
        </nav>
        <p className="px-3 text-xs leading-relaxed text-muted-foreground">
          Data: Cricsheet (ODC-BY). Not affiliated with the IPL or BCCI.
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
