"use client";

import { CornerDownLeft, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { useCompetition } from "@/components/competition/use-competition";
import { COMPETITIONS, competitionPath, type CompetitionId } from "@/lib/competitions";
import { PRIMARY_NAV, SECONDARY_NAV, isAvailable, isShown, navHref } from "@/lib/navigation";
import { filterResults, groupResults, type SearchResult } from "@/lib/search";
import { cn } from "@/lib/utils";

interface Extras {
  teams: { id: string; name: string; color: string; active: boolean }[];
  matches: { match_id: number; headline: string; detail: string }[];
}

interface PlayerHit {
  player_id: string;
  name: string;
  role: string | null;
  team: string | null;
  seasons: string;
}

const ROLE: Record<string, string> = {
  batter: "Batter",
  bowler: "Bowler",
  all_rounder: "All-rounder",
  keeper: "Wicketkeeper",
};

function pages(competition: CompetitionId): SearchResult[] {
  return [...PRIMARY_NAV, ...SECONDARY_NAV]
    .filter((item) => isAvailable(item) && isShown(item, competition))
    .map((item) => ({
      id: `page:${item.label}`,
      group: "Pages" as const,
      label: item.label,
      href: navHref(item, competition),
    }));
}

const competitions: SearchResult[] = COMPETITIONS.map((c) => ({
  id: `competition:${c.id}`,
  group: "Competitions",
  label: c.label,
  detail: c.name,
  href: competitionPath(c.id),
}));

/** Teams and featured replays of a competition, fetched once per competition per visit. */
const extrasCache = new Map<CompetitionId, Promise<Extras>>();
function loadExtras(competition: CompetitionId): Promise<Extras> {
  let found = extrasCache.get(competition);
  if (!found) {
    found = fetch(`/api/${competition}/search`)
      .then((r) => (r.ok ? (r.json() as Promise<Extras>) : { teams: [], matches: [] }))
      .catch(() => ({ teams: [], matches: [] }));
    extrasCache.set(competition, found);
  }
  return found;
}

/** Search pages, competitions, players, teams and featured replays; Enter goes there. */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const competition = useCompetition();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [extras, setExtras] = useState<Extras | null>(null);
  const [players, setPlayers] = useState<{ q: string; items: PlayerHit[] } | null>(null);
  const listId = useId();
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    let live = true;
    loadExtras(competition).then((e) => live && setExtras(e));
    return () => {
      live = false;
    };
  }, [open, competition]);

  // Players are searched by the API as you type (from two letters, after a short pause).
  const q = query.trim();
  useEffect(() => {
    if (q.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetch(`/api/${competition}/players?q=${encodeURIComponent(q)}`, {
        signal: controller.signal,
      })
        .then((r) => r.json() as Promise<{ items: PlayerHit[] }>)
        .then((body) => setPlayers({ q, items: body.items ?? [] }))
        .catch(() => {});
    }, 180);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [q, competition]);

  const groups = useMemo(() => {
    const playerResults: SearchResult[] =
      q.length >= 2 && players?.q === q
        ? players.items.map((p) => ({
            id: `player:${p.player_id}`,
            group: "Players",
            label: p.name,
            detail: [p.role ? ROLE[p.role] : null, p.team, p.seasons].filter(Boolean).join(" · "),
            href: competitionPath(competition, `/players/${p.player_id}`),
          }))
        : [];
    const teams: SearchResult[] = (extras?.teams ?? []).map((t) => ({
      id: `team:${t.id}`,
      group: "Teams",
      label: t.name,
      detail: t.id,
      href: competitionPath(competition, `/teams/${t.id}`),
      color: t.color,
    }));
    const matches: SearchResult[] = (extras?.matches ?? []).map((m) => ({
      id: `match:${m.match_id}`,
      group: "Featured replays",
      label: m.headline,
      detail: m.detail,
      href: competitionPath(competition, `/matches/${m.match_id}`),
    }));
    return groupResults([
      ...filterResults(q, pages(competition)),
      ...filterResults(q, competitions),
      ...playerResults,
      // Teams only once something is typed: there are too many to list.
      ...(q ? filterResults(q, teams) : []),
      ...filterResults(q, matches),
    ]);
  }, [q, players, extras, competition]);

  const flat = groups.flatMap((g) => g.items);
  const current = flat[Math.min(active, flat.length - 1)];

  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-result-id="${CSS.escape(current?.id ?? "")}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [current?.id]);

  function go(result: SearchResult | undefined) {
    if (!result) return;
    onOpenChange(false);
    router.push(result.href);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    const last = flat.length - 1;
    const move: Record<string, () => number> = {
      ArrowDown: () => (active >= last ? 0 : active + 1),
      ArrowUp: () => (active <= 0 ? last : active - 1),
      Home: () => 0,
      End: () => last,
    };
    if (move[event.key] && flat.length) {
      event.preventDefault();
      setActive(move[event.key]());
    } else if (event.key === "Enter") {
      event.preventDefault();
      go(current);
    }
  }

  const optionId = (r: SearchResult) => `${listId}-${r.id.replace(/[^a-zA-Z0-9_-]/g, "_")}`;

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setQuery("");
          setActive(0);
        }
        onOpenChange(next);
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
        {/* Springs open from 95% (only fades with reduced motion, app/globals.css); fades out
                on close. */}
        <DialogPrimitive.Content aria-describedby={undefined} asChild>
          <div className="palette-panel fixed top-[12vh] left-1/2 z-50 flex max-h-[70vh] w-[min(40rem,calc(100vw-2rem))] -translate-x-1/2 flex-col overflow-hidden rounded-2xl border border-border bg-popover text-popover-foreground shadow-elev-3 outline-none data-closed:animate-out data-closed:fade-out-0">
            <DialogPrimitive.Title className="sr-only">Search</DialogPrimitive.Title>
            <div className="flex items-center gap-3 border-b border-border px-4">
              <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <input
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={current ? optionId(current) : undefined}
                aria-label="Search pages, players, teams and matches"
                placeholder="Search pages, players, teams and matches…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={onKeyDown}
                className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="hidden rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">
                Esc
              </kbd>
            </div>
            <div
              ref={listRef}
              id={listId}
              role="listbox"
              aria-label="Results"
              className="flex-1 overflow-y-auto p-2"
            >
              {groups.map(({ group, items }) => (
                <div key={group} role="group" aria-labelledby={`${listId}-${group}`}>
                  <div
                    id={`${listId}-${group}`}
                    className="px-2 pt-2 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
                  >
                    {group}
                  </div>
                  {items.map((r) => {
                    const selected = r.id === current?.id;
                    return (
                      <div
                        key={r.id}
                        id={optionId(r)}
                        data-result-id={r.id}
                        role="option"
                        aria-selected={selected}
                        onMouseMove={() => setActive(flat.indexOf(r))}
                        onClick={() => go(r)}
                        className={cn(
                          "flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm",
                          selected && "bg-accent text-accent-foreground",
                        )}
                      >
                        {r.color && (
                          <span
                            aria-hidden="true"
                            className="size-2.5 shrink-0 rounded-full ring-1 ring-foreground/15"
                            style={{ backgroundColor: r.color }}
                          />
                        )}
                        <span className="min-w-0 flex-1 truncate">
                          <span className="font-medium">{r.label}</span>
                          {r.detail && (
                            <span className="ml-2 text-xs text-muted-foreground">{r.detail}</span>
                          )}
                        </span>
                        {selected && (
                          <CornerDownLeft
                            className="size-3.5 shrink-0 text-muted-foreground"
                            aria-hidden="true"
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
              {groups.length === 0 && (
                <p className="px-3 py-8 text-center text-sm text-muted-foreground">
                  Nothing matches &ldquo;{q}&rdquo;.
                </p>
              )}
            </div>
            <p className="sr-only" aria-live="polite">
              {flat.length === 1 ? "1 result" : `${flat.length} results`}
            </p>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
