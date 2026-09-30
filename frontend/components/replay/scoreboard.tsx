import { TeamSwatch } from "@/components/match/team-badge";
import type { Timeline } from "@/lib/api/types";
import { formatRate } from "@/lib/cricket";
import { formatScore, inningsLabel } from "@/lib/format";
import { type Frame, scoreState } from "@/lib/replay/engine";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className="font-mono text-base tabular-nums">{value}</span>
    </div>
  );
}

export function Scoreboard({
  timeline,
  frame,
  atEnd,
}: {
  timeline: Timeline;
  frame: Frame | null;
  atEnd: boolean;
}) {
  const { summary, teams } = timeline;

  if (!frame) {
    const toss = summary.toss;
    return (
      <section aria-label="Scoreboard" className="glass rounded-2xl p-6">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          Before the first ball
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
          or the play button to start the replay.
        </p>
      </section>
    );
  }

  const state = scoreState(frame);
  const batting = teams[frame.innings.batting_team_id];
  const chasing = state.target !== null;

  return (
    <section aria-label="Scoreboard" className="glass rounded-2xl p-6">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          {inningsLabel(frame.innings.innings_no, frame.innings.is_super_over)}
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
          {state.wickets === 10 && <span className="text-2xl text-muted-foreground"> all out</span>}
        </span>
        <span className="font-mono text-lg text-muted-foreground tabular-nums">
          ({state.overs})
        </span>
      </div>

      <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
        <Stat label="Run rate" value={formatRate(state.runRate)} />
        {chasing && (
          <>
            <Stat label="Target" value={String(state.target)} />
            <Stat
              label="Required rate"
              value={
                atEnd || !state.runsNeeded || !state.ballsRemaining
                  ? "—"
                  : formatRate(state.requiredRate)
              }
            />
          </>
        )}
      </div>

      {chasing && !atEnd && state.runsNeeded! > 0 && (
        <p className="mt-4 text-sm">
          Need <span className="font-mono font-semibold tabular-nums">{state.runsNeeded}</span> from{" "}
          <span className="font-mono font-semibold tabular-nums">{state.ballsRemaining}</span> balls
        </p>
      )}

      {atEnd && (
        <p className="mt-4 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-foreground">
          {summary.result_text}
        </p>
      )}
    </section>
  );
}
