import { TeamSwatch } from "@/components/match/team-badge";
import { OutcomeBar } from "@/components/replay/test/outcome-bar";
import type { Timeline } from "@/lib/api/types";
import { formatRate } from "@/lib/cricket";
import { formatScore, inningsLabel } from "@/lib/format";
import { type Frame, scoreState } from "@/lib/replay/engine";
import { dayAt, type Outcome, situation } from "@/lib/replay/test";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className="font-mono text-base tabular-nums">{value}</span>
    </div>
  );
}

/** The scoreboard of a Test replay: the innings, where the match stands and the day. */
export function TestScoreboard({
  timeline,
  frame,
  cursor,
  atEnd,
  outcome,
}: {
  timeline: Timeline;
  frame: Frame | null;
  cursor: number;
  atEnd: boolean;
  outcome: Outcome | null;
}) {
  const { summary, teams } = timeline;
  const day = dayAt(timeline, cursor);

  if (!frame) {
    const toss = summary.toss;
    return (
      <section aria-label="Scoreboard" className="glass rounded-2xl p-6">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          Before the first ball{day ? " · Day 1" : ""}
        </p>
        <p className="mt-3 text-2xl font-semibold tracking-tight">
          {summary.team_a.name} <span className="text-muted-foreground">vs</span>{" "}
          {summary.team_b.name}
        </p>
        {toss.winner_name && (
          <p className="mt-2 text-sm text-muted-foreground">
            {toss.winner_name} won the toss and chose to {toss.decision}.
          </p>
        )}
        <p className="mt-4 text-sm text-muted-foreground">
          Press <kbd className="rounded border border-border px-1.5 font-mono text-xs">Space</kbd>{" "}
          or the play button to start the replay. A Test is about 2,000 balls: the faster speeds and
          the jumps below cover a day in minutes.
        </p>
        <OutcomeBar timeline={timeline} outcome={outcome} />
      </section>
    );
  }

  const state = scoreState(frame);
  const batting = teams[frame.innings.batting_team_id];
  const where = situation(timeline, cursor);
  const declared = frame.isInningsEnd && frame.innings.declared;

  return (
    <section aria-label="Scoreboard" className="glass rounded-2xl p-6">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          {inningsLabel(frame.innings.innings_no, false)}
          {frame.innings.follow_on && " · following on"}
          {day ? ` · Day ${day} (est.)` : ""}
        </p>
        <p className="font-mono text-xs text-muted-foreground">Ball {frame.delivery.ball_label}</p>
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="flex items-center gap-2 text-lg font-medium">
          <TeamSwatch color={batting.color} />
          {batting.name}
        </span>
        <span
          className="font-mono text-5xl font-semibold tracking-tight tabular-nums"
          aria-live="polite"
          aria-atomic="true"
        >
          {formatScore(state.runs, state.wickets === 10 ? 10 : state.wickets)}
          {declared && <span className="text-2xl text-muted-foreground"> declared</span>}
          {state.wickets === 10 && <span className="text-2xl text-muted-foreground"> all out</span>}
        </span>
        <span className="font-mono text-lg text-muted-foreground tabular-nums">
          ({state.overs})
        </span>
      </div>

      <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
        <Stat label="Run rate" value={formatRate(state.runRate)} />
        <Stat label="Partnership" value={`${frame.partnership.runs}`} />
      </div>

      {where && !atEnd && <p className="mt-4 text-sm font-medium">{where}</p>}

      {atEnd && (
        <p className="mt-4 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-foreground">
          {summary.result_text}
        </p>
      )}

      <OutcomeBar timeline={timeline} outcome={outcome} />
    </section>
  );
}
