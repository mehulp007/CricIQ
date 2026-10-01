"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import { type PickedPlayer, PlayerPicker } from "@/components/matchups/player-picker";
import { cn } from "@/lib/utils";

/** Batter and bowler pickers; the pair lives in the URL so every matchup is a link. */
export function MatchupSelector({
  batter,
  bowler,
}: {
  batter: PickedPlayer | null;
  bowler: PickedPlayer | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  function set(key: "batter" | "bowler", player: PickedPlayer | null) {
    const next = new URLSearchParams(params);
    if (player) next.set(key, player.player_id);
    else next.delete(key);
    next.delete("page");
    const query = next.toString();
    startTransition(() =>
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false }),
    );
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
        label="Batter"
        role="batter"
        value={batter}
        onChange={(p) => set("batter", p)}
      />
      <span className="hidden pb-2.5 text-sm text-muted-foreground sm:block">vs</span>
      <PlayerPicker
        label="Bowler"
        role="bowler"
        value={bowler}
        onChange={(p) => set("bowler", p)}
      />
    </div>
  );
}
