import { GitCompareArrows } from "lucide-react";

import { TeamBadge } from "@/components/match/team-badge";
import type { StyleGroup } from "@/lib/api/types";
import { compareHref } from "@/lib/compare";
import { roleLabel } from "@/lib/players";
import { CompetitionLink } from "@/components/competition/competition-link";

function Trait({ children }: { children: string }) {
  return (
    <li className="rounded-md bg-muted/60 px-2 py-0.5 text-[11px] text-muted-foreground">
      {children}
    </li>
  );
}

/** The closest style profiles in the same seasons, each one click from a comparison. */
export function SimilarPlayers({
  group,
  playerId,
  role,
  window,
}: {
  group: StyleGroup;
  playerId: string;
  role: "batting" | "bowling";
  window: { from?: number; to?: number };
}) {
  const query = new URLSearchParams();
  if (window.from) query.set("from", String(window.from));
  if (window.to) query.set("to", String(window.to));
  const suffix = query.toString() ? `?${query}` : "";
  return (
    <div className="flex flex-col gap-4">
      {group.traits.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Style:</span>
          <ul className="flex flex-wrap gap-1.5" aria-label="Distinctive traits">
            {group.traits.map((t) => (
              <Trait key={t}>{t}</Trait>
            ))}
          </ul>
        </div>
      )}
      <ol className="flex flex-col divide-y divide-border">
        {group.items.map((p) => (
          <li key={p.player_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
            <span
              className="w-12 font-mono text-sm font-semibold tabular-nums"
              title="Cosine similarity of the two style profiles"
            >
              {Math.round(p.similarity * 100)}%<span className="sr-only"> similar</span>
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <CompetitionLink
                  href={`/players/${p.player_id}${suffix}`}
                  className="truncate text-sm font-medium underline-offset-4 hover:text-primary hover:underline"
                >
                  {p.name}
                </CompetitionLink>
                {p.team && <TeamBadge shortName={p.team.franchise_id} color={p.team.color} />}
                <span className="text-xs text-muted-foreground">{roleLabel(p.role, false)}</span>
              </span>
              {p.shared.length > 0 && (
                <ul className="flex flex-wrap gap-1.5" aria-label={`Shared with ${p.name}`}>
                  {p.shared.map((t) => (
                    <Trait key={t}>{t}</Trait>
                  ))}
                </ul>
              )}
            </div>
            <CompetitionLink
              href={compareHref(playerId, p.player_id, { ...window, role })}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-2.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label={`Compare with ${p.name}`}
            >
              <GitCompareArrows className="size-3.5" aria-hidden="true" />
              Compare
            </CompetitionLink>
          </li>
        ))}
      </ol>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Among {group.population} players with {group.min_balls}+ balls in these seasons. A profile
        is a handful of per-ball rates against par and how the player is used; the percentage is how
        closely two profiles point the same way.
      </p>
    </div>
  );
}
