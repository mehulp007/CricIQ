"use client";

import { ArrowLeftRight } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface TeamOption {
  id: string;
  name: string;
  active: boolean;
}

function TeamSelect({
  label,
  value,
  teams,
  disabled,
  onChange,
}: {
  label: string;
  value: string | undefined;
  teams: TeamOption[];
  disabled: string | undefined;
  onChange: (id: string) => void;
}) {
  const groups: [string, TeamOption[]][] = [
    ["Current", teams.filter((t) => t.active)],
    ["Former", teams.filter((t) => !t.active)],
  ];
  return (
    <Select value={value ?? ""} onValueChange={onChange}>
      <SelectTrigger className="w-full sm:w-64" aria-label={label}>
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        {groups.map(([group, options]) => (
          <SelectGroup key={group}>
            <SelectLabel>{group}</SelectLabel>
            {options.map((t) => (
              <SelectItem key={t.id} value={t.id} disabled={t.id === disabled}>
                {t.name}
              </SelectItem>
            ))}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  );
}

/** Two franchises for the head-to-head page; the choice lives in the URL (?a=&b=). */
export function TeamPicker({
  teams,
  a,
  b,
}: {
  teams: TeamOption[];
  a: string | undefined;
  b: string | undefined;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function go(nextA: string | undefined, nextB: string | undefined) {
    const next = new URLSearchParams(params);
    for (const [key, value] of [
      ["a", nextA],
      ["b", nextB],
    ] as const) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    // A new pair may not share the old season window.
    next.delete("from");
    next.delete("to");
    startTransition(() => router.push(`${pathname}?${next}`, { scroll: false }));
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-2 transition-opacity sm:flex-row sm:items-center",
        pending && "opacity-60",
      )}
      aria-busy={pending}
    >
      <TeamSelect
        label="First team"
        value={a}
        teams={teams}
        disabled={b}
        onChange={(id) => go(id, b)}
      />
      <button
        type="button"
        onClick={() => go(b, a)}
        disabled={!a || !b}
        className="inline-flex h-9 w-9 items-center justify-center self-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
        aria-label="Swap teams"
      >
        <ArrowLeftRight className="size-4" aria-hidden="true" />
      </button>
      <TeamSelect
        label="Second team"
        value={b}
        teams={teams}
        disabled={a}
        onChange={(id) => go(a, id)}
      />
    </div>
  );
}
