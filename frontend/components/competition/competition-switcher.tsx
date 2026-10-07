"use client";

import { usePathname, useRouter } from "next/navigation";
import { useTransition } from "react";

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
import {
  COMPETITIONS,
  UPCOMING,
  getCompetition,
  isCompetitionId,
  switchPath,
} from "@/lib/competitions";
import { cn } from "@/lib/utils";

const LEAGUES = COMPETITIONS.filter((c) => c.teamType === "club");
const INTERNATIONALS = COMPETITIONS.filter((c) => c.teamType === "national");

/**
 * Picks the competition the site shows. Switching keeps the same kind of page
 * (matches stay matches); a page about one match, player or team goes to its list.
 */
export function CompetitionSwitcher({ className }: { className?: string }) {
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
      <SelectContent align="end">
        <SelectGroup>
          <SelectLabel>Leagues</SelectLabel>
          {LEAGUES.map((c) => (
            <SelectItem key={c.id} value={c.id} textValue={c.label}>
              <span className="font-medium">{c.label}</span>
              <span className="hidden text-xs text-muted-foreground sm:inline">{c.name}</span>
            </SelectItem>
          ))}
        </SelectGroup>
        <SelectSeparator />
        <SelectGroup>
          <SelectLabel>Internationals</SelectLabel>
          {INTERNATIONALS.map((c) => (
            <SelectItem key={c.id} value={c.id} textValue={c.label}>
              <span className="font-medium">{c.label}</span>
              <span className="hidden text-xs text-muted-foreground sm:inline">{c.name}</span>
            </SelectItem>
          ))}
          {UPCOMING.map((f) => (
            <SelectItem key={f.label} value={`upcoming-${f.label}`} disabled textValue={f.label}>
              <span className="font-medium">{f.label}</span>
              <span className="text-xs text-muted-foreground">coming in {f.milestone}</span>
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
