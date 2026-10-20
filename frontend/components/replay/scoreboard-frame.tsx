"use client";

import { AnimatePresence, m } from "motion/react";
import type { ReactNode } from "react";

import { TeamSwatch } from "@/components/match/team-badge";
import { usePrefersReducedMotion } from "@/lib/animation";
import type { Timeline } from "@/lib/api/types";
import { formatScore } from "@/lib/format";
import type { LiveInningsCard } from "@/lib/replay/engine";
import { cn } from "@/lib/utils";

/**
 * A score whose changing characters flip: the old one slides up and fades as the new one rises
 * from below, like a stadium scoreboard. Characters are matched from the right, so the wickets
 * stay put when the runs gain a digit ("99/3" to "100/3"). Screen readers (and anything reading
 * the page) get the score as plain text; reduced motion just shows it.
 */
export function FlipScore({ text, className }: { text: string; className?: string }) {
  const reduced = usePrefersReducedMotion();
  const chars = [...text];
  return (
    <span className={cn("inline-flex", className)}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" className="inline-flex">
        {chars.map((char, i) => (
          <span
            key={chars.length - i}
            className="relative inline-block overflow-hidden whitespace-pre"
          >
            {reduced ? (
              char
            ) : (
              <AnimatePresence mode="popLayout" initial={false}>
                <m.span
                  key={char}
                  className="inline-block"
                  initial={{ y: "70%", opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: "-70%", opacity: 0 }}
                  transition={{ type: "spring", stiffness: 520, damping: 34 }}
                >
                  {char}
                </m.span>
              </AnimatePresence>
            )}
          </span>
        ))}
      </span>
    </span>
  );
}

/** A stat under the live score: a small label over its value. */
export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className="font-mono text-base tabular-nums">{value}</span>
    </div>
  );
}

function inningsScore(card: LiveInningsCard): string {
  const declared = card.complete && card.innings.declared ? "d" : "";
  return `${formatScore(card.runs, card.wickets)}${declared}`;
}

/**
 * Both sides' innings so far (super overs aside), the side batting marked: "MI 149/8 (20)" and
 * "CSK 148/7 (20)", or in a Test "ENG 67 & 362/9".
 */
function SidesStrip({
  timeline,
  cards,
  battingTeamId,
  withOvers,
}: {
  timeline: Timeline;
  cards: LiveInningsCard[];
  battingTeamId: string | null;
  withOvers: boolean;
}) {
  const sides = [timeline.summary.team_a, timeline.summary.team_b];
  return (
    <dl className="grid grid-cols-2 border-b border-border/70 text-sm">
      {sides.map((team, i) => {
        const innings = cards.filter(
          (c) => c.innings.batting_team_id === team.team_season_id && !c.innings.is_super_over,
        );
        const batting = team.team_season_id === battingTeamId;
        return (
          <div
            key={team.team_season_id}
            className={cn(
              "flex min-w-0 items-center justify-between gap-2 px-5 py-2.5 sm:px-6",
              i === 1 && "border-l border-border/70",
              batting && "bg-accent/50",
            )}
          >
            <dt className="flex min-w-0 items-center gap-2">
              <TeamSwatch color={team.color} />
              <span className="font-medium">{team.franchise_id}</span>
              {batting && (
                // On phones the shaded cell alone marks the side batting.
                <span className="hidden rounded-full bg-primary/15 px-1.5 py-px text-[10px] font-medium text-foreground uppercase sm:inline">
                  Batting
                </span>
              )}
            </dt>
            <dd
              className={cn(
                "min-w-0 truncate text-right font-mono tabular-nums",
                batting ? "font-semibold text-foreground" : "text-muted-foreground",
              )}
            >
              {innings.length > 0 ? (
                <>
                  <FlipScore text={innings.map(inningsScore).join(" & ")} />
                  {withOvers && (
                    <span className="hidden sm:inline"> ({innings.at(-1)!.overs})</span>
                  )}
                </>
              ) : (
                "Yet to bat"
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/**
 * The scoreboard's frame, shared by the limited-overs and Test replays: a header with the innings
 * and the ball, both sides' scores, then the live detail.
 */
export function ScoreboardFrame({
  timeline,
  cards,
  battingTeamId,
  withOvers,
  heading,
  ball,
  children,
}: {
  timeline: Timeline;
  cards: LiveInningsCard[];
  battingTeamId: string | null;
  withOvers: boolean;
  heading: ReactNode;
  ball?: string;
  children: ReactNode;
}) {
  return (
    <section aria-label="Scoreboard" className="glass overflow-hidden rounded-2xl">
      <div className="flex items-center justify-between gap-3 border-b border-border/70 bg-muted/40 px-5 py-2.5 sm:px-6">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {heading}
        </p>
        {ball && <p className="font-mono text-xs text-muted-foreground">Ball {ball}</p>}
      </div>
      <SidesStrip
        timeline={timeline}
        cards={cards}
        battingTeamId={battingTeamId}
        withOvers={withOvers}
      />
      <div className="p-5 sm:p-6">{children}</div>
    </section>
  );
}
