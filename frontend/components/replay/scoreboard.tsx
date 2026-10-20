import { TeamSwatch } from "@/components/match/team-badge";
import { FlipScore, ScoreboardFrame, Stat } from "@/components/replay/scoreboard-frame";
import { WinProbabilityBar } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import { formatRate } from "@/lib/cricket";
import { formatScore, inningsLabel } from "@/lib/format";
import { type Frame, type LiveInningsCard, scoreState } from "@/lib/replay/engine";
import { pressureAt } from "@/lib/replay/pressure";

export function Scoreboard({
  timeline,
  frame,
  cards,
  atEnd,
  wp,
}: {
  timeline: Timeline;
  frame: Frame | null;
  cards: LiveInningsCard[];
  atEnd: boolean;
  wp: number | null;
}) {
  const { summary, teams } = timeline;
  // The pressure on the next ball, for the glow around the win-probability bar.
  const pressure = pressureAt(timeline, frame ? frame.index : -1)?.pressure ?? null;

  if (!frame) {
    const toss = summary.toss;
    return (
      <ScoreboardFrame
        timeline={timeline}
        cards={cards}
        battingTeamId={null}
        withOvers
        heading="Before the first ball"
      >
        <p className="text-2xl font-semibold tracking-tight">
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
        <WinProbabilityBar timeline={timeline} wp={wp} pressure={pressure} />
      </ScoreboardFrame>
    );
  }

  const state = scoreState(frame);
  const batting = teams[frame.innings.batting_team_id];
  const chasing = state.target !== null;

  return (
    <ScoreboardFrame
      timeline={timeline}
      cards={cards}
      battingTeamId={frame.innings.batting_team_id}
      withOvers
      heading={inningsLabel(frame.innings.innings_no, frame.innings.is_super_over)}
      ball={frame.delivery.ball_label ?? undefined}
    >
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="flex items-center gap-2 text-lg font-medium">
          <TeamSwatch color={batting.color} />
          {batting.name}
        </span>
        <span
          className="font-mono text-5xl font-semibold tracking-tight tabular-nums"
          aria-live="polite"
          aria-atomic="true"
        >
          <FlipScore text={formatScore(state.runs, state.wickets === 10 ? 10 : state.wickets)} />
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

      <WinProbabilityBar timeline={timeline} wp={wp} pressure={pressure} />
    </ScoreboardFrame>
  );
}
