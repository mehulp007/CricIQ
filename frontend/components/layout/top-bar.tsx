import Link from "next/link";
import { Suspense } from "react";

import { Logo } from "@/components/brand/logo";
import { DataBadges, SeasonBadge } from "@/components/layout/data-badges";
import { MobileNav } from "@/components/layout/mobile-nav";

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-md lg:px-8">
      <MobileNav />
      <Link href="/" className="lg:hidden" aria-label="CricIQ home">
        <Logo />
      </Link>
      <div className="ml-auto flex items-center gap-2">
        <Suspense fallback={<SeasonBadge />}>
          <DataBadges />
        </Suspense>
      </div>
    </header>
  );
}
