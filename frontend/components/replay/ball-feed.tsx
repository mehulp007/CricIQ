import { ArrowLeftRight } from "lucide-react";

import { BallChip } from "@/components/replay/ball-chip";
import type { Timeline } from "@/lib/api/types";
import { type Frame, playerName } from "@/lib/replay/engine";
import { cn } from "@/lib/utils";

const FEED_LENGTH = 14;

type FeedItem =
  { kind: "ball"; key: string; frame: Frame } | { kind: "sub"; key: string; text: string };

const REASONS: Record<string, string> = {
  impact_player: "Impact Player",
  concussion_substitute: "Concussion substitute",
};

export function BallFeed({
  timeline,
  frames,
  cursor,
}: {
  timeline: Timeline;
  frames: Frame[];
  cursor: number;
}) {
  const items: FeedItem[] = [];
  for (let i = cursor; i >= 0 && items.length < FEED_LENGTH; i--) {
    const frame = frames[i];
    const d = frame.delivery;
    for (const sub of timeline.substitutions) {
      if (sub.innings_no === d.innings_no && sub.seq_no === d.seq_no) {
        const team = timeline.teams[sub.team_season_id]?.franchise_id ?? "";
        items.push({
          kind: "sub",
          key: `sub-${sub.innings_no}-${sub.seq_no}-${sub.player_in_id}`,
          text: `${REASONS[sub.reason ?? ""] ?? "Substitute"} (${team}): ${
            sub.player_in_id ? playerName(timeline, sub.player_in_id) : "?"
          } replaces ${sub.player_out_id ? playerName(timeline, sub.player_out_id) : "?"}`,
        });
      }
    }
    items.push({ kind: "ball", key: `ball-${i}`, frame });
  }

  return (
    <section
      aria-label="Ball by ball"
      className="flex min-h-0 flex-col rounded-2xl border border-border bg-card/70 p-5"
    >
      <h2 className="text-xs tracking-wide text-muted-foreground uppercase">Ball by ball</h2>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">
          Commentary appears as the replay plays.
        </p>
      ) : (
        <ol className="mt-3 flex flex-col divide-y divide-border" aria-live="polite">
          {items.map((item, position) =>
            item.kind === "sub" ? (
              <li key={item.key} className="flex items-center gap-3 py-2.5 text-xs text-team-b">
                <ArrowLeftRight className="size-4 shrink-0" aria-hidden="true" />
                {item.text}
              </li>
            ) : (
              <li
                key={item.key}
                className={cn(
                  "flex items-start gap-3 py-2.5 text-sm transition-opacity",
                  position > 0 && "opacity-80",
                )}
              >
                <span className="w-9 shrink-0 pt-1 font-mono text-xs text-muted-foreground tabular-nums">
                  {item.frame.delivery.ball_label}
                </span>
                <BallChip delivery={item.frame.delivery} className="shrink-0" />
                <span
                  className={cn(
                    "pt-0.5 leading-snug",
                    item.frame.delivery.wicket?.is_dismissal && "font-medium text-wicket",
                  )}
                >
                  {item.frame.commentary}
                </span>
              </li>
            ),
          )}
        </ol>
      )}
    </section>
  );
}
