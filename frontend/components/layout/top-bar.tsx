import Link from "next/link";
import { Suspense } from "react";

import { Logo } from "@/components/brand/logo";
import { CompetitionSwitcher } from "@/components/competition/competition-switcher";
import { DataFreshness } from "@/components/layout/data-badges";
import { SearchTrigger } from "@/components/search/search-trigger";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { competitionCards } from "@/lib/shell";

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-background/80 px-4 backdrop-blur-md sm:gap-3 lg:px-8">
      <Link href="/" className="lg:hidden" aria-label="CricIQ home">
        <Logo />
      </Link>
      <SearchTrigger className="ml-auto lg:ml-0 lg:w-64" />
      <div className="flex items-center gap-2 lg:ml-auto">
        <Suspense fallback={null}>
          <DataFreshness />
        </Suspense>
        <CompetitionSwitcher cards={competitionCards()} />
        <ThemeToggle />
      </div>
    </header>
  );
}
