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

export interface FilterChoice {
  value: string;
  label: string;
}

/** One select in a filter bar, stored in the URL as ``param``. */
export interface FilterField {
  param: string;
  /** The select's accessible name ("Batting team"). */
  label: string;
  /** What "no filter" reads as ("All teams"). */
  all: string;
  choices: FilterChoice[];
  /** Tailwind width of the trigger. */
  width?: string;
}

/** Search params with ``key`` set to ``value`` (removed for "all" or null), back on page 1. */
export function withParam(
  params: URLSearchParams | { toString(): string },
  key: string,
  value: string | null,
): URLSearchParams {
  const next = new URLSearchParams(params.toString());
  if (value === null || value === ALL || value === "") next.delete(key);
  else next.set(key, value);
  next.delete("page");
  return next;
}

/**
 * Filters that live in the URL, so every view is shareable and rendered on the server:
 * season range, team, opponent, ground, innings or anything a page passes in ``fields``.
 */
export function FilterBar({ fields, className }: { fields: FilterField[]; className?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function update(key: string, value: string | null) {
    const next = withParam(params, key, value);
    const query = next.toString();
    startTransition(() =>
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false }),
    );
  }

  const active = fields.some((f) => params.has(f.param));

  return (
    <div
      role="group"
      aria-label="Filters"
      className={cn(
        "flex flex-wrap items-center gap-2 transition-opacity",
        pending && "opacity-60",
        className,
      )}
      aria-busy={pending}
    >
      {fields.map((field) => (
        <Select
          key={field.param}
          value={params.get(field.param) ?? ALL}
          onValueChange={(v) => update(field.param, v)}
        >
          <SelectTrigger className={field.width ?? "w-44"} aria-label={field.label}>
            <SelectValue placeholder={field.label} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{field.all}</SelectItem>
            {field.choices.map((choice) => (
              <SelectItem key={choice.value} value={choice.value}>
                {choice.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ))}
      {active && (
        <Button
          variant="ghost"
          size="lg"
          onClick={() => {
            let next = new URLSearchParams(params.toString());
            for (const field of fields) next = withParam(next, field.param, null);
            const query = next.toString();
            startTransition(() =>
              router.push(query ? `${pathname}?${query}` : pathname, { scroll: false }),
            );
          }}
        >
          Clear filters
        </Button>
      )}
    </div>
  );
}
