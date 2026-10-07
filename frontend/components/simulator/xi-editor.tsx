"use client";

import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SimSeasonTeam, SquadPlayer } from "@/lib/api/types";
import { roleLabel } from "@/lib/players";
import { useCompetition } from "@/components/competition/use-competition";
import { seasonLabel } from "@/lib/competitions";
import {
  MIN_BOWLERS,
  XI_SIZE,
  type XIState,
  addPlayer,
  bench,
  move,
  removePlayer,
  sideIssue,
} from "@/lib/simulator";
import { cn } from "@/lib/utils";

function role(p: SquadPlayer): string | null {
  return p.role ? roleLabel(p.role as "batter" | "bowler" | "all_rounder", false) : null;
}

function xiMeta(p: SquadPlayer): string {
  const bowls = p.recent_overs > 0;
  const parts = [
    role(p),
    bowls && p.bowling_type ? p.bowling_type : null,
    bowls ? `${Math.round(p.recent_overs)} recent overs` : null,
  ];
  return parts.filter(Boolean).join(" · ");
}

function benchMeta(p: SquadPlayer): string {
  const parts = [
    role(p),
    p.recent_overs > 0 && p.bowling_type ? p.bowling_type : null,
    `${p.matches} ${p.matches === 1 ? "match" : "matches"}`,
  ];
  return parts.filter(Boolean).join(" · ");
}

const iconButton = "rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-30";

/** One side: its team that season, the XI picked from its squad, batting order and bowlers. */
export function XIEditor({
  label,
  color,
  season,
  teams,
  xi,
  busy,
  onTeam,
  onChange,
}: {
  label: string;
  color: string;
  season: number | null;
  teams: SimSeasonTeam[];
  xi: XIState;
  busy: boolean;
  onTeam: (team: string) => void;
  onChange: (xi: XIState) => void;
}) {
  const competition = useCompetition();
  const issue = sideIssue(xi);
  const bowlerCount = xi.bowlers.filter((id) => xi.players.some((p) => p.player_id === id)).length;
  const rest = bench(xi);
  const full = xi.players.length >= XI_SIZE;
  const teamName = teams.find((t) => t.team.franchise_id === xi.team)?.display_name;

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
        <Select value={xi.team ?? ""} onValueChange={onTeam} disabled={busy}>
          <SelectTrigger className="w-60" aria-label={`${label} team`}>
            <SelectValue placeholder="Pick a team" />
          </SelectTrigger>
          <SelectContent>
            {teams.map((t) => (
              <SelectItem key={t.team.franchise_id} value={t.team.franchise_id}>
                {t.display_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <h3 className="text-xs tracking-wide text-muted-foreground uppercase">
          Playing XI · {xi.players.length}/{XI_SIZE}
        </h3>
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
                  <span className="block truncate text-[11px] text-muted-foreground">
                    {xiMeta(p)}
                  </span>
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
                    className={iconButton}
                    aria-label={`Move ${p.name} up`}
                  >
                    <ArrowUp className="size-3.5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onChange({ ...xi, players: move(xi.players, i, i + 1) })}
                    disabled={i === xi.players.length - 1}
                    className={iconButton}
                    aria-label={`Move ${p.name} down`}
                  >
                    <ArrowDown className="size-3.5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onChange(removePlayer(xi, p.player_id))}
                    className={iconButton}
                    aria-label={`Leave ${p.name} out`}
                  >
                    <X className="size-3.5" aria-hidden="true" />
                  </button>
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      <p
        className={cn("text-xs", issue ? "text-negative" : "text-muted-foreground")}
        aria-live="polite"
      >
        {issue ??
          `${bowlerCount} bowling options (at least ${MIN_BOWLERS}). Order is the batting order.`}
      </p>

      {rest.length > 0 && (
        <div className="flex flex-col gap-1 rounded-xl bg-muted/30 p-3">
          <h3 className="text-xs tracking-wide text-muted-foreground uppercase">
            Rest of the squad · {rest.length}
          </h3>
          <p className="text-[11px] text-muted-foreground">
            {teamName && season
              ? `Everyone else who played for ${teamName} in ${seasonLabel(competition, season)}. `
              : ""}
            {full ? "Leave someone out of the XI to bring a player in." : "Add players to the XI."}
          </p>
          <ul className="flex flex-col divide-y divide-border" aria-label={`${label} squad`}>
            {rest.map((p) => (
              <li key={p.player_id} className="flex items-center gap-2 py-1.5">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm">{p.name}</span>
                  <span className="block truncate text-[11px] text-muted-foreground">
                    {benchMeta(p)}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => onChange(addPlayer(xi, p.player_id))}
                  disabled={full}
                  className="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-border px-2 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
                  aria-label={`Add ${p.name} to the XI`}
                >
                  <Plus className="size-3.5" aria-hidden="true" />
                  Add
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
