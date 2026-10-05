"use client";

import { ArrowDown, ArrowUp, X } from "lucide-react";
import { useState } from "react";

import { PlayerPicker } from "@/components/matchups/player-picker";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SimPlayer, SimXI } from "@/lib/api/types";
import { roleLabel } from "@/lib/players";
import { MIN_BOWLERS, XI_SIZE, type XIState, move, sideIssue } from "@/lib/simulator";
import { cn } from "@/lib/utils";

export interface TeamOption {
  id: string;
  name: string;
  active: boolean;
}

function meta(p: SimPlayer): string {
  const bowls = p.recent_overs > 0;
  const parts = [
    p.role ? roleLabel(p.role as "batter" | "bowler" | "all_rounder", false) : null,
    bowls && p.bowling_type ? p.bowling_type : null,
    bowls ? `${Math.round(p.recent_overs)} recent overs` : null,
  ];
  return parts.filter(Boolean).join(" · ");
}

/** One side's XI: team, batting order and bowling options, all editable. */
export function XIEditor({
  label,
  color,
  teams,
  xi,
  busy,
  onTeam,
  onChange,
}: {
  label: string;
  color: string;
  teams: TeamOption[];
  xi: XIState;
  busy: boolean;
  onTeam: (team: string) => void;
  onChange: (xi: XIState) => void;
}) {
  const [adding, setAdding] = useState<"idle" | "loading" | "error">("idle");
  const issue = sideIssue(xi);
  const bowlerCount = xi.bowlers.filter((id) => xi.players.some((p) => p.player_id === id)).length;

  async function add(playerId: string) {
    if (xi.players.some((p) => p.player_id === playerId)) return;
    setAdding("loading");
    try {
      const response = await fetch("/api/simulate/xi", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ player_ids: [playerId] }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const found = (await response.json()) as SimXI;
      const player = found.players[0];
      onChange({
        ...xi,
        players: [...xi.players, player],
        bowlers:
          found.bowlers.includes(player.player_id) && player.recent_overs >= 4
            ? [...xi.bowlers, player.player_id]
            : xi.bowlers,
      });
      setAdding("idle");
    } catch {
      setAdding("error");
    }
  }

  const groups: [string, TeamOption[]][] = [
    ["Current", teams.filter((t) => t.active)],
    ["Former", teams.filter((t) => !t.active)],
  ];

  return (
    <section
      aria-label={label}
      className={cn(
        "flex min-w-0 flex-col gap-4 rounded-2xl border border-border bg-card/70 p-4 transition-opacity sm:p-5",
        busy && "opacity-60",
      )}
      aria-busy={busy}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <span
            aria-hidden="true"
            className="size-2.5 rounded-full"
            style={{ background: color }}
          />
          {label}
        </h2>
        <Select value={xi.team ?? ""} onValueChange={onTeam}>
          <SelectTrigger className="w-56" aria-label={`${label} team`}>
            <SelectValue placeholder="Pick a team" />
          </SelectTrigger>
          <SelectContent>
            {groups.map(([group, options]) => (
              <SelectGroup key={group}>
                <SelectLabel>{group}</SelectLabel>
                {options.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      </div>

      <ol className="flex flex-col divide-y divide-border" aria-label={`${label} batting order`}>
        {xi.players.map((p, i) => {
          const bowls = xi.bowlers.includes(p.player_id);
          return (
            <li key={p.player_id} className="flex items-center gap-2 py-1.5">
              <span className="w-5 shrink-0 text-right font-mono text-xs text-muted-foreground tabular-nums">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm">{p.name}</span>
                <span className="block truncate text-[11px] text-muted-foreground">{meta(p)}</span>
              </span>
              <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={bowls}
                  onChange={() =>
                    onChange({
                      ...xi,
                      bowlers: bowls
                        ? xi.bowlers.filter((id) => id !== p.player_id)
                        : [...xi.bowlers, p.player_id],
                    })
                  }
                  className="size-4 accent-[var(--primary)]"
                  aria-label={`${p.name} bowls`}
                />
                <span aria-hidden="true">Bowls</span>
              </label>
              <span className="flex shrink-0">
                <button
                  type="button"
                  onClick={() => onChange({ ...xi, players: move(xi.players, i, i - 1) })}
                  disabled={i === 0}
                  className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
                  aria-label={`Move ${p.name} up`}
                >
                  <ArrowUp className="size-3.5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => onChange({ ...xi, players: move(xi.players, i, i + 1) })}
                  disabled={i === xi.players.length - 1}
                  className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
                  aria-label={`Move ${p.name} down`}
                >
                  <ArrowDown className="size-3.5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    onChange({
                      ...xi,
                      players: xi.players.filter((q) => q.player_id !== p.player_id),
                      bowlers: xi.bowlers.filter((id) => id !== p.player_id),
                    })
                  }
                  className="rounded p-1 text-muted-foreground hover:text-foreground"
                  aria-label={`Remove ${p.name}`}
                >
                  <X className="size-3.5" aria-hidden="true" />
                </button>
              </span>
            </li>
          );
        })}
      </ol>

      {xi.players.length < XI_SIZE && (
        <div className="flex flex-col gap-1">
          <PlayerPicker
            label={`Add a player to ${label}`}
            value={null}
            role="batter"
            placeholder="Search any IPL player"
            onChange={(picked) => picked && add(picked.player_id)}
          />
          {adding === "loading" && (
            <p className="text-xs text-muted-foreground" aria-live="polite">
              Adding…
            </p>
          )}
          {adding === "error" && (
            <p className="text-xs text-negative" aria-live="polite">
              Could not add that player. Try again.
            </p>
          )}
        </div>
      )}

      <p
        className={cn("text-xs", issue ? "text-negative" : "text-muted-foreground")}
        aria-live="polite"
      >
        {issue ??
          `${bowlerCount} bowling options (at least ${MIN_BOWLERS}). Order is the batting order.`}
      </p>
    </section>
  );
}
