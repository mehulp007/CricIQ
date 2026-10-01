"use client";

import { Search, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PLAYER_SORTS, ROLE_FILTERS } from "@/lib/players";
import { cn } from "@/lib/utils";

const ALL = "all";
const SEARCH_DELAY_MS = 300;

export interface PlayerFilterOptions {
  seasons: number[];
  teams: { id: string; name: string; active: boolean }[];
}

/** Search and filters live in the URL so every view is shareable and server-rendered. */
export function PlayerFilters({ options }: { options: PlayerFilterOptions }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const lastPushed = useRef(params.get("q") ?? "");

  function push(next: URLSearchParams) {
    next.delete("page");
    const search = next.toString();
    startTransition(() =>
      router.replace(search ? `${pathname}?${search}` : pathname, { scroll: false }),
    );
  }

  function update(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value === null || value === ALL) next.delete(key);
    else next.set(key, value);
    push(next);
  }

  // Search as you type, once typing pauses.
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed === lastPushed.current) return;
    const timer = setTimeout(() => {
      lastPushed.current = trimmed;
      const next = new URLSearchParams(params);
      if (trimmed) next.set("q", trimmed);
      else next.delete("q");
      push(next);
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the typed query triggers a search
  }, [query]);

  const active = ["q", "role", "season", "team", "sort"].some((k) => params.has(k));

  return (
    <div
      className={cn(
        "flex flex-col gap-3 transition-opacity lg:flex-row lg:flex-wrap lg:items-center",
        pending && "opacity-60",
      )}
      aria-busy={pending}
    >
      <label className="relative flex w-full items-center lg:w-72">
        <span className="sr-only">Search players</span>
        <Search
          className="pointer-events-none absolute left-3 size-4 text-muted-foreground"
          aria-hidden="true"
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, e.g. Bumrah"
          autoComplete="off"
          spellCheck={false}
          className="h-9 w-full rounded-lg border border-input bg-transparent pr-9 pl-9 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30 [&::-webkit-search-cancel-button]:hidden"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            className="absolute right-2 rounded p-1 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={params.get("role") ?? ALL} onValueChange={(v) => update("role", v)}>
          <SelectTrigger className="w-40" aria-label="Role">
            <SelectValue placeholder="Role" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All roles</SelectItem>
            {ROLE_FILTERS.map((r) => (
              <SelectItem key={r.value} value={r.value}>
                {r.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={params.get("season") ?? ALL} onValueChange={(v) => update("season", v)}>
          <SelectTrigger className="w-36" aria-label="Season">
            <SelectValue placeholder="Season" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All seasons</SelectItem>
            {options.seasons.map((year) => (
              <SelectItem key={year} value={String(year)}>
                {year}
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

        <Select value={params.get("sort") ?? "matches"} onValueChange={(v) => update("sort", v)}>
          <SelectTrigger className="w-40" aria-label="Sort by">
            <SelectValue placeholder="Sort" />
          </SelectTrigger>
          <SelectContent>
            {PLAYER_SORTS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {active && (
          <Button
            variant="ghost"
            size="lg"
            onClick={() => {
              setQuery("");
              lastPushed.current = "";
              startTransition(() => router.replace(pathname, { scroll: false }));
            }}
          >
            Clear
          </Button>
        )}
      </div>
    </div>
  );
}
