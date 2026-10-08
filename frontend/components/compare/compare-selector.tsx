"use client";

import { ArrowLeftRight } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import { useCompetition } from "@/components/competition/use-competition";
import { type PickedPlayer, PlayerPicker } from "@/components/matchups/player-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { COMPETITIONS, type CompetitionId } from "@/lib/competitions";
import { cn } from "@/lib/utils";

/** Two player pickers, each in a competition of its own (the page's by default); the
 * pair lives in the URL so every comparison is a link. */
export function CompareSelector({
  a,
  b,
  af,
  bf,
}: {
  a: PickedPlayer | null;
  b: PickedPlayer | null;
  af?: CompetitionId;
  bf?: CompetitionId;
}) {
  const page = useCompetition();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function go(next: URLSearchParams) {
    // A different pair may not share the chosen role or seasons.
    next.delete("role");
    const query = next.toString();
    startTransition(() =>
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false }),
    );
  }

  function set(key: "a" | "b", player: PickedPlayer | null) {
    const next = new URLSearchParams(params);
    if (player) next.set(key, player.player_id);
    else next.delete(key);
    go(next);
  }

  function setFormat(key: "af" | "bf", value: string) {
    const next = new URLSearchParams(params);
    if (value === page) next.delete(key);
    else next.set(key, value);
    go(next);
  }

  function swap() {
    const next = new URLSearchParams(params);
    if (a) next.set("b", a.player_id);
    else next.delete("b");
    if (b) next.set("a", b.player_id);
    else next.delete("a");
    for (const [from, to] of [
      [af, "bf"],
      [bf, "af"],
    ] as const) {
      if (from) next.set(to, from);
      else next.delete(to);
    }
    startTransition(() => router.push(`${pathname}?${next}`, { scroll: false }));
  }

  return (
    <div
      className={cn(
        "grid gap-3 transition-opacity sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-end",
        pending && "opacity-60",
      )}
      aria-busy={pending}
    >
      <div className="flex min-w-0 flex-col gap-2">
        <PlayerPicker
          label="Player A"
          role="batter"
          placeholder="Search a player"
          value={a}
          onChange={(p) => set("a", p)}
          competition={af ?? page}
        />
        <FormatSelect
          label="Competition of the first player"
          value={af ?? page}
          onChange={(v) => setFormat("af", v)}
        />
      </div>
      <button
        type="button"
        onClick={swap}
        disabled={!a && !b}
        className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg border border-border px-3 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
        aria-label="Swap players"
      >
        <ArrowLeftRight className="size-4" aria-hidden="true" />
        <span className="sm:sr-only">Swap</span>
      </button>
      <div className="flex min-w-0 flex-col gap-2">
        <PlayerPicker
          label="Player B"
          role="batter"
          placeholder="Search a player"
          value={b}
          onChange={(p) => set("b", p)}
          competition={bf ?? page}
        />
        <FormatSelect
          label="Competition of the second player"
          value={bf ?? page}
          onChange={(v) => setFormat("bf", v)}
        />
      </div>
    </div>
  );
}

function FormatSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: CompetitionId;
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full sm:w-48" aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {COMPETITIONS.map((c) => (
          <SelectItem key={c.id} value={c.id}>
            In {c.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
