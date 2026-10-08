"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DRAW_COLOR } from "@/components/replay/test/outcome-bar";
import { SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { ChaseOutcome, ChaseWhatIf, Timeline } from "@/lib/api/types";
import { competitionPath, type CompetitionId } from "@/lib/competitions";
import { pointsText } from "@/lib/simulator";
import { formatPercent } from "@/lib/replay/win-probability";
import { cn } from "@/lib/utils";
import { fetchAwake, wakeSimulator } from "@/lib/wake";

function Stepper({
  label,
  value,
  steps,
  allowed,
  onChange,
}: {
  label: string;
  value: string;
  steps: number[];
  allowed: (step: number) => boolean;
  onChange: (delta: number) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      <div className="flex flex-wrap items-center gap-1" role="group" aria-label={label}>
        {steps.map((step) => (
          <button
            key={step}
            type="button"
            disabled={!allowed(step)}
            onClick={() => onChange(step)}
            className="h-7 min-w-9 rounded-md border border-border px-2 font-mono text-xs text-muted-foreground tabular-nums transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
            aria-label={`${step > 0 ? "Add" : "Remove"} ${Math.abs(step)} ${label.toLowerCase()}`}
          >
            {step > 0 ? `+${step}` : `−${-step}`}
          </button>
        ))}
        <span className="ml-1 font-mono text-sm font-semibold tabular-nums">{value}</span>
      </div>
    </div>
  );
}

function Chances({ outcome, side }: { outcome: ChaseOutcome; side: "a" | "b" }) {
  const parts = [
    ["Win", outcome.won, SIDE_COLORS[side]],
    ["Draw", outcome.drawn, DRAW_COLOR],
    ["Lose", outcome.lost, SIDE_COLORS[side === "a" ? "b" : "a"]],
  ] as const;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
        {parts.map(([label, value]) => (
          <span key={label} className="flex items-baseline gap-1.5">
            {label}
            <span className="font-mono text-sm text-foreground tabular-nums">
              {formatPercent(value)}
            </span>
          </span>
        ))}
      </div>
      <div
        role="img"
        aria-label={`Win ${formatPercent(outcome.won)}, draw ${formatPercent(outcome.drawn)}, lose ${formatPercent(outcome.lost)}`}
        className="flex h-1.5 gap-0.5 overflow-hidden rounded-full"
      >
        {parts.map(([label, value, color]) => (
          <span
            key={label}
            className="h-full transition-[width] duration-500 ease-out"
            style={{
              width: `${value * 100}%`,
              background: color,
              opacity: label === "Draw" ? 0.5 : 1,
            }}
          />
        ))}
      </div>
    </div>
  );
}

/** The fourth-innings ball the what-if starts from: the cursor's, or null outside the chase. */
function chaseBall(timeline: Timeline, cursor: number): number | null {
  const d = cursor >= 0 ? timeline.deliveries[cursor] : null;
  if (!d || d.innings_no !== 4) return null;
  const next = timeline.deliveries[cursor + 1];
  return next ? d.seq_no : null; // the last ball is the result
}

/**
 * Tests: what if the chasing side needed more or fewer runs, had more or fewer wickets
 * in hand, or more or less time? The Test win probability model answers from the
 * edited state, with the rest of the match's context unchanged.
 */
export function ChasePanel({
  timeline,
  cursor,
  competition,
}: {
  timeline: Timeline;
  cursor: number;
  competition: CompetitionId;
}) {
  const seq = chaseBall(timeline, cursor);
  useEffect(() => wakeSimulator(), []);
  if (seq === null) return null;
  return <ChaseWhatIfView key={seq} timeline={timeline} seq={seq} competition={competition} />;
}

function ChaseWhatIfView({
  timeline,
  seq,
  competition,
}: {
  timeline: Timeline;
  seq: number;
  competition: CompetitionId;
}) {
  const [needed, setNeeded] = useState(0);
  const [wickets, setWickets] = useState(0);
  const [overs, setOvers] = useState(0);
  const [result, setResult] = useState<ChaseWhatIf | null>(null);
  const [status, setStatus] = useState<"loading" | "waking" | "ready" | "error">("loading");
  const real = result?.real ?? null;
  const changed = needed !== 0 || wickets !== 0 || overs !== 0;

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({
      match: String(timeline.summary.match_id),
      seq: String(seq),
    });
    if (real) {
      params.set("needed", String(Math.max(real.runs_needed + needed, 1)));
      params.set("wickets", String(Math.min(Math.max(real.wickets_in_hand + wickets, 1), 10)));
      params.set("overs", String(Math.max(real.overs_left + overs, 0)));
    }
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetchAwake(`/api/${competition}/chase?${params}`, undefined, () =>
          setStatus("waking"),
        );
        if (!response.ok) throw new Error(String(response.status));
        const found = (await response.json()) as ChaseWhatIf;
        if (!cancelled) {
          setResult(found);
          setStatus("ready");
        }
      } catch {
        if (!cancelled) setStatus("error");
      }
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // `real` is the API's first answer; later answers keep it, so it is not a trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needed, wickets, overs, seq, competition, timeline.summary.match_id]);

  const side =
    timeline.summary.team_b.team_season_id === result?.batting_team.team_season_id ? "b" : "a";
  const edited = result?.edited ?? null;
  return (
    <section
      aria-label="Chase what-if"
      className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs tracking-wide text-muted-foreground uppercase">Chase what-if</h2>
        <span className="rounded-md border border-border px-2 py-0.5 text-[10px] tracking-wide text-muted-foreground uppercase">
          Model estimate
        </span>
      </div>
      {real === null || edited === null ? (
        <p aria-live="polite" className="text-sm text-muted-foreground">
          {status === "error"
            ? "The what-if is unavailable right now. Try again in a moment."
            : status === "waking"
              ? "Waking the server. The free server sleeps when nobody is using it, so this can take up to a minute…"
              : "Loading the chase…"}
        </p>
      ) : (
        <>
          <p className="text-sm">
            {result?.batting_team.franchise_id} need{" "}
            <span className="font-mono tabular-nums">{real.runs_needed}</span> with{" "}
            <span className="font-mono tabular-nums">{real.wickets_in_hand}</span>{" "}
            {real.wickets_in_hand === 1 ? "wicket" : "wickets"} in hand and about{" "}
            <span className="font-mono tabular-nums">{Math.round(real.overs_left)}</span> overs
            left. Change the chase:
          </p>
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <Stepper
              label="Runs needed"
              value={String(edited.runs_needed)}
              steps={[-25, -10, 10, 25]}
              allowed={(d) => real.runs_needed + needed + d >= 1 && needed + d <= 400}
              onChange={(d) => setNeeded((v) => v + d)}
            />
            <Stepper
              label="Wickets in hand"
              value={String(edited.wickets_in_hand)}
              steps={[-1, 1]}
              allowed={(d) => {
                const w = real.wickets_in_hand + wickets + d;
                return w >= 1 && w <= 10;
              }}
              onChange={(d) => setWickets((v) => v + d)}
            />
            <Stepper
              label="Overs left"
              value={String(Math.round(edited.overs_left))}
              steps={[-20, -10, 10, 20]}
              allowed={(d) => {
                const o = real.overs_left + overs + d;
                return o >= 0 && o <= 450;
              }}
              onChange={(d) => setOvers((v) => v + d)}
            />
          </div>
          <div aria-live="polite" className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-[11px] tracking-wide text-muted-foreground uppercase">
                {changed ? "With your changes" : "As it was"}
              </span>
              <Chances outcome={edited} side={side} />
            </div>
            {changed && (
              <p className="text-sm">
                <span className="font-mono font-semibold tabular-nums">
                  {formatPercent(edited.won)}
                </span>{" "}
                <span className="text-muted-foreground">
                  win chance, from {formatPercent(real.won)}
                </span>{" "}
                <span
                  className={cn(
                    "font-mono text-sm tabular-nums",
                    edited.won >= real.won ? "text-positive" : "text-negative",
                  )}
                >
                  {pointsText(edited.won * 100 - real.won * 100)}
                </span>
              </p>
            )}
          </div>
          {changed && (
            <button
              type="button"
              onClick={() => {
                setNeeded(0);
                setWickets(0);
                setOvers(0);
              }}
              className="inline-flex h-8 w-fit items-center gap-1.5 rounded-lg border border-border px-3 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              The real chase
            </button>
          )}
          <p className="text-xs leading-relaxed text-muted-foreground">
            The Test win probability model, run on the edited chase; the sides and the ground stay
            as they were. Overs left are estimated (five days of 90 overs less those bowled).{" "}
            <Link
              href={competitionPath(competition, "/models")}
              className="text-foreground underline-offset-4 hover:underline"
            >
              How
            </Link>
          </p>
        </>
      )}
    </section>
  );
}
