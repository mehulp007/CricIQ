"use client";

import { ArrowLeftRight } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import { type PickedPlayer, PlayerPicker } from "@/components/matchups/player-picker";
import { cn } from "@/lib/utils";

/** Two player pickers; the pair lives in the URL so every comparison is a link. */
export function CompareSelector({ a, b }: { a: PickedPlayer | null; b: PickedPlayer | null }) {
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

  function swap() {
    const next = new URLSearchParams(params);
    if (a) next.set("b", a.player_id);
    else next.delete("b");
    if (b) next.set("a", b.player_id);
    else next.delete("a");
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
      <PlayerPicker
        label="Player A"
        role="batter"
        placeholder="Search a player"
        value={a}
        onChange={(p) => set("a", p)}
      />
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
      <PlayerPicker
        label="Player B"
        role="batter"
        placeholder="Search a player"
        value={b}
        onChange={(p) => set("b", p)}
      />
    </div>
  );
}
