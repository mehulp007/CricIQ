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

export interface SeriesFilterOptions {
  years: number[];
  teams: { id: string; name: string }[];
}

/** Year, side and kind, kept in the URL so every view is shareable and server-rendered. */
export function SeriesFilters({ options }: { options: SeriesFilterOptions }) {
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

  const active = ["year", "team", "kind"].some((k) => params.has(k));

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 transition-opacity",
        pending && "opacity-60",
      )}
      aria-busy={pending}
    >
      <Select value={params.get("year") ?? ALL} onValueChange={(v) => update("year", v)}>
        <SelectTrigger className="w-32" aria-label="Year">
          <SelectValue placeholder="Year" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All years</SelectItem>
          {options.years.map((year) => (
            <SelectItem key={year} value={String(year)}>
              {year}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={params.get("team") ?? ALL} onValueChange={(v) => update("team", v)}>
        <SelectTrigger className="w-56" aria-label="Side">
          <SelectValue placeholder="Side" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All sides</SelectItem>
          {options.teams.map((team) => (
            <SelectItem key={team.id} value={team.id}>
              {team.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={params.get("kind") ?? ALL} onValueChange={(v) => update("kind", v)}>
        <SelectTrigger className="w-40" aria-label="Kind">
          <SelectValue placeholder="Kind" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Series and tournaments</SelectItem>
          <SelectItem value="series">Series</SelectItem>
          <SelectItem value="tournament">Tournaments</SelectItem>
        </SelectContent>
      </Select>

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
