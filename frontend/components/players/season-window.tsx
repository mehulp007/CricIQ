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
import { useCompetition } from "@/components/competition/use-competition";
import { cn } from "@/lib/utils";

/** First season of the IPL's Impact Player rule, which changed scoring rates. */
const IMPACT_PLAYER_ERA = 2023;

/**
 * Season window for every number on the profile. It lives in the URL, so a
 * window is shareable and server-rendered; the full career needs no params.
 */
export function SeasonWindow({
  career,
  first,
  last,
  allLabel = "Career",
}: {
  career: [number, number];
  first: number;
  last: number;
  /** Label of the preset covering every season. */
  allLabel?: string;
}) {
  const competition = useCompetition();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();
  const seasons = Array.from({ length: career[1] - career[0] + 1 }, (_, i) => career[0] + i);

  function go(from: number, to: number) {
    const next = new URLSearchParams(params);
    const [low, high] = from <= to ? [from, to] : [to, from];
    if (low <= career[0]) next.delete("from");
    else next.set("from", String(low));
    if (high >= career[1]) next.delete("to");
    else next.set("to", String(high));
    const query = next.toString();
    startTransition(() =>
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false }),
    );
  }

  const presets = [
    { label: allLabel, from: career[0], to: career[1] },
    { label: "Last 3 seasons", from: Math.max(career[0], career[1] - 2), to: career[1] },
    ...(competition === "ipl" && career[1] >= IMPACT_PLAYER_ERA && career[0] < IMPACT_PLAYER_ERA
      ? [{ label: "Impact Player era", from: IMPACT_PLAYER_ERA, to: career[1] }]
      : []),
  ].filter((p, i, all) => all.findIndex((q) => q.from === p.from && q.to === p.to) === i);

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 transition-opacity",
        pending && "opacity-60",
      )}
      aria-busy={pending}
    >
      <span className="text-sm text-muted-foreground">Seasons</span>
      <Select value={String(first)} onValueChange={(v) => go(Number(v), last)}>
        <SelectTrigger className="w-24" aria-label="From season">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {seasons.map((y) => (
            <SelectItem key={y} value={String(y)}>
              {y}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <span className="text-sm text-muted-foreground">to</span>
      <Select value={String(last)} onValueChange={(v) => go(first, Number(v))}>
        <SelectTrigger className="w-24" aria-label="To season">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {seasons.map((y) => (
            <SelectItem key={y} value={String(y)}>
              {y}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="flex flex-wrap gap-1.5">
        {presets.map((p) => {
          const on = p.from === first && p.to === last;
          return (
            <button
              key={p.label}
              type="button"
              aria-pressed={on}
              onClick={() => go(p.from, p.to)}
              className={cn(
                "h-8 rounded-lg border px-3 text-xs transition-colors",
                on
                  ? "border-primary/50 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {p.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
