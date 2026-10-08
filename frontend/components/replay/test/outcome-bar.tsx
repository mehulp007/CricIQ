import { ModelEstimateNote, SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import type { Outcome } from "@/lib/replay/test";
import { formatPercent } from "@/lib/replay/win-probability";

/** The draw's colour between the two sides'. */
export const DRAW_COLOR = "var(--muted-foreground)";

/** A Test's three results: the side batting first wins, a draw, the other side wins. */
export function OutcomeBar({ timeline, outcome }: { timeline: Timeline; outcome: Outcome | null }) {
  if (outcome === null) return null;
  const { team_a, team_b } = timeline.summary;
  const parts = [
    { key: "a", label: team_a.franchise_id, value: outcome.a, color: SIDE_COLORS.a },
    { key: "draw", label: "Draw", value: outcome.draw, color: DRAW_COLOR },
    { key: "b", label: team_b.franchise_id, value: outcome.b, color: SIDE_COLORS.b },
  ];
  const label =
    `Result chances: ${team_a.name} win ${formatPercent(outcome.a)}, ` +
    `draw ${formatPercent(outcome.draw)}, ${team_b.name} win ${formatPercent(outcome.b)}`;

  return (
    <div className="mt-5 flex flex-col gap-2" data-testid="outcome-probability">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] tracking-wide text-muted-foreground uppercase">
          Result chances
        </span>
        <ModelEstimateNote />
      </div>
      <div className="grid grid-cols-3 gap-2 text-sm">
        {parts.map((p, i) => (
          <span
            key={p.key}
            className={
              i === 0
                ? "flex items-center gap-2"
                : i === 1
                  ? "flex items-center justify-center gap-2"
                  : "flex items-center justify-end gap-2"
            }
          >
            <span
              aria-hidden="true"
              className="size-2 rounded-full"
              style={{ background: p.color }}
            />
            {p.label}
            <span className="font-mono text-base font-semibold tabular-nums">
              {formatPercent(p.value)}
            </span>
          </span>
        ))}
      </div>
      <div role="img" aria-label={label} className="flex h-2 gap-0.5 overflow-hidden rounded-full">
        {parts.map((p) => (
          <span
            key={p.key}
            className="h-full transition-[width] duration-500 ease-out"
            style={{
              width: `${Math.round(p.value * 1000) / 10}%`,
              background: p.color,
              opacity: p.key === "draw" ? 0.5 : 1,
            }}
          />
        ))}
      </div>
    </div>
  );
}
