"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

/** Picks the season shown in the league table; it lives in the URL (?season=). */
export function SeasonPicker({
  seasons,
  season,
}: {
  seasons: { year: number; label: string }[];
  season: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();
  const latest = Math.max(...seasons.map((s) => s.year));

  function go(value: string) {
    const next = new URLSearchParams(params);
    if (Number(value) === latest) next.delete("season");
    else next.set("season", value);
    const query = next.toString();
    startTransition(() =>
      router.push(query ? `${pathname}?${query}#table` : `${pathname}#table`, { scroll: false }),
    );
  }

  return (
    <div className={cn("transition-opacity", pending && "opacity-60")} aria-busy={pending}>
      <Select value={String(season)} onValueChange={go}>
        <SelectTrigger className="w-28" aria-label="League table season">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {[...seasons].reverse().map(({ year, label }) => (
            <SelectItem key={year} value={String(year)}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
