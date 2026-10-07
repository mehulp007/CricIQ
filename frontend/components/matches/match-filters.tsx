"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const ALL = "all";

export interface FilterOptions {
  seasons: { year: number; label: string }[];
  teams: { id: string; name: string; active: boolean }[];
}

/** Filters live in the URL so every view is shareable and server-rendered. */
export function MatchFilters({ options }: { options: FilterOptions }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function update(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value === null || value === ALL) next.delete(key);
    else next.set(key, value);
    next.delete("page");
    startTransition(() => router.push(`${pathname}?${next}`, { scroll: false }));
  }

  const playoffs = params.get("playoffs") === "true";
  const active = ["season", "team", "playoffs"].some((k) => params.has(k));

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 transition-opacity",
        pending && "opacity-60",
      )}
      aria-busy={pending}
    >
      <Select value={params.get("season") ?? ALL} onValueChange={(v) => update("season", v)}>
        <SelectTrigger className="w-36" aria-label="Season">
          <SelectValue placeholder="Season" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All seasons</SelectItem>
          {options.seasons.map(({ year, label }) => (
            <SelectItem key={year} value={String(year)}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={params.get("team") ?? ALL} onValueChange={(v) => update("team", v)}>
        <SelectTrigger className="w-56" aria-label="Team">
          <SelectValue placeholder="Team" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All teams</SelectItem>
          {options.teams.map((team) => (
            <SelectItem key={team.id} value={team.id}>
              {team.name}
              {!team.active && <span className="text-muted-foreground"> (defunct)</span>}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        variant={playoffs ? "secondary" : "outline"}
        size="lg"
        aria-pressed={playoffs}
        onClick={() => update("playoffs", playoffs ? null : "true")}
      >
        Playoffs only
      </Button>

      {active && (
        <Button
          variant="ghost"
          size="lg"
          onClick={() => startTransition(() => router.push(pathname, { scroll: false }))}
        >
          Clear
        </Button>
      )}
    </div>
  );
}
