"use client";

import { Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { roleLabel } from "@/lib/players";
import type { PlayerRole } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export interface PickedPlayer {
  player_id: string;
  name: string;
}

interface Option extends PickedPlayer {
  role: PlayerRole;
  is_keeper: boolean;
  team: string | null;
  seasons: string;
}

const SEARCH_DELAY_MS = 200;

/** Accessible search-as-you-type combobox over the player directory. */
export function PlayerPicker({
  label,
  value,
  role,
  placeholder,
  onChange,
}: {
  label: string;
  value: PickedPlayer | null;
  role: "batter" | "bowler";
  placeholder?: string;
  onChange: (player: PickedPlayer | null) => void;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<Option[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setStatus("loading");
      try {
        // Not filtered by role: part-time bowlers and all-rounders bowl too.
        const response = await fetch(`/api/players?q=${encodeURIComponent(q)}`, {
          signal: controller.signal,
        });
        const body = (await response.json()) as { items: Option[] };
        setOptions(body.items);
        setActive(0);
        setStatus(response.ok ? "idle" : "error");
      } catch (error) {
        if ((error as Error).name !== "AbortError") setStatus("error");
      }
    }, SEARCH_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  function pick(option: Option) {
    onChange({ player_id: option.player_id, name: option.name });
    setQuery("");
    setOptions([]);
    setOpen(false);
  }

  if (value) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-xs tracking-wide text-muted-foreground uppercase">{label}</span>
        <div className="flex h-10 items-center justify-between gap-2 rounded-lg border border-primary/40 bg-primary/5 px-3">
          <span className="truncate text-sm font-medium">{value.name}</span>
          <button
            type="button"
            onClick={() => {
              onChange(null);
              requestAnimationFrame(() => inputRef.current?.focus());
            }}
            className="rounded p-1 text-muted-foreground hover:text-foreground"
            aria-label={`Clear ${label.toLowerCase()}`}
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    );
  }

  const showList = open && query.trim().length >= 2;
  return (
    <div className="relative flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs tracking-wide text-muted-foreground uppercase">
        {label}
      </label>
      <div className="relative">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && options[active] ? `${listId}-${active}` : undefined}
          value={query}
          placeholder={placeholder ?? (role === "batter" ? "Search a batter" : "Search a bowler")}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            if (e.target.value.trim().length < 2) setOptions([]);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, options.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && options[active]) {
              e.preventDefault();
              pick(options[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          className="h-10 w-full rounded-lg border border-input bg-transparent pr-3 pl-9 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30"
        />
      </div>
      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label={`${label} results`}
          className="absolute top-full z-20 mt-1 max-h-80 w-full overflow-y-auto rounded-lg border border-border bg-popover p-1 shadow-lg"
        >
          {options.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground" aria-live="polite">
              {status === "loading"
                ? "Searching…"
                : status === "error"
                  ? "Search is waking up. Try again in a moment."
                  : "No players found."}
            </li>
          ) : (
            options.map((option, i) => (
              <li
                key={option.player_id}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(option);
                }}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  "flex cursor-pointer items-baseline justify-between gap-3 rounded-md px-3 py-2 text-sm",
                  i === active && "bg-muted",
                )}
              >
                <span className="truncate">{option.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {roleLabel(option.role, option.is_keeper)}
                  {option.team && ` · ${option.team}`} · {option.seasons}
                </span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
