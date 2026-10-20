"use client";

import { usePathname, useRouter } from "next/navigation";
import { useTransition, type CSSProperties } from "react";

import { useCompetition } from "@/components/competition/use-competition";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getCompetition, isCompetitionId, switchPath } from "@/lib/competitions";
import type { CompetitionCard } from "@/lib/shell";
import { cn } from "@/lib/utils";

const GROUPS = ["Leagues", "Internationals"] as const;

/**
 * Picks the competition the site shows, as cards with each one's format and years. Switching
 * keeps the same kind of page (matches stay matches); a page about one match, player or team goes
 * to its list.
 */
export function CompetitionSwitcher({
  cards,
  className,
}: {
  cards: CompetitionCard[];
  className?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const competition = useCompetition();
  const [pending, startTransition] = useTransition();

  function choose(value: string) {
    if (!isCompetitionId(value)) return;
    startTransition(() => router.push(switchPath(pathname, value)));
  }

  return (
    <Select value={competition} onValueChange={choose}>
      <SelectTrigger
        aria-label="Competition"
        data-testid="competition-switcher"
        className={cn(
          "h-8 w-28 font-medium transition-opacity",
          pending && "opacity-60",
          className,
        )}
      >
        <SelectValue>{getCompetition(competition).label}</SelectValue>
      </SelectTrigger>
      <SelectContent position="popper" align="end" className="w-[min(34rem,calc(100vw-2rem))]">
        {GROUPS.map((group, i) => (
          <SelectGroup key={group} className="p-1">
            {i > 0 && <SelectSeparator className="mb-2" />}
            <SelectLabel>{group}</SelectLabel>
            <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
              {cards
                .filter((c) => c.group === group)
                .map((c) => (
                  <SelectItem
                    key={c.id}
                    value={c.id}
                    textValue={c.label}
                    // Cards arrive one after another as the list opens (app/globals.css).
                    style={{ "--i": cards.indexOf(c) } as CSSProperties}
                    className="switcher-card items-start rounded-lg border border-transparent py-2 data-[state=checked]:border-primary/40 data-[state=checked]:bg-primary/5"
                  >
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="flex items-baseline gap-2">
                        <span className="font-mono text-sm font-semibold">{c.label}</span>
                        <span className="truncate text-xs text-muted-foreground">{c.name}</span>
                      </span>
                      <span className="text-[11px] text-muted-foreground">{c.detail}</span>
                    </span>
                  </SelectItem>
                ))}
            </div>
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  );
}
