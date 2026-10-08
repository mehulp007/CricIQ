import Link from "next/link";

import { SIDE_COLORS } from "@/components/replay/win-probability-bar";
import type { Timeline } from "@/lib/api/types";
import { competitionPath, getCompetition, type CompetitionId } from "@/lib/competitions";
import {
  PRESSURE_BANDS,
  formatLeverage,
  momentumAt,
  pressureAt,
  pressureBand,
} from "@/lib/replay/pressure";

const PRESSURE_COLOR = "var(--chart-4)";
const MOMENTUM_SCALE = 30; // points at the end of the bar

function sideOf(inningsNo: number): "a" | "b" {
  return inningsNo === 1 ? "a" : "b";
}

function PressureMeter({ pressure }: { pressure: number }) {
  const edges = [...PRESSURE_BANDS.map((b) => b.from), 100];
  return (
    <span className="relative block h-3" aria-hidden="true">
      {PRESSURE_BANDS.map((band, i) => (
        <span
          key={band.label}
          className="absolute inset-y-0.5 rounded-sm"
          style={{
            left: `${edges[i]}%`,
            width: `calc(${edges[i + 1] - edges[i]}% - 2px)`,
            background: PRESSURE_COLOR,
            opacity: 0.12 + 0.2 * i,
          }}
        />
      ))}
      <span
        className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
        style={{ left: `${pressure}%`, background: PRESSURE_COLOR }}
      />
    </span>
  );
}

function MomentumBar({ points, color }: { points: number; color: string }) {
  const width = (Math.min(Math.abs(points), MOMENTUM_SCALE) / MOMENTUM_SCALE) * 50;
  return (
    <span className="relative block h-3" aria-hidden="true">
      <span className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted" />
      <span className="absolute -inset-y-0.5 left-1/2 w-px bg-foreground/40" />
      <span
        className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full"
        style={{
          left: points >= 0 ? "50%" : `${50 - width}%`,
          width: `${width}%`,
          background: color,
        }}
      />
    </span>
  );
}

/** How much the next ball matters, and which way the last two overs went. */
export function PressurePanel({
  timeline,
  cursor,
  competition,
}: {
  timeline: Timeline;
  cursor: number;
  competition: CompetitionId;
}) {
  const c = getCompetition(competition);
  const reading = pressureAt(timeline, cursor);
  const momentum = momentumAt(timeline, cursor);
  if (!reading && !momentum) return null;
  const { team_a, team_b } = timeline.summary;

  return (
    <section
      aria-label="Pressure and momentum"
      className="grid gap-5 rounded-2xl border border-border bg-card/70 p-5 sm:grid-cols-2"
    >
      <div className="flex flex-col gap-2">
        <h2 className="text-xs tracking-wide text-muted-foreground uppercase">
          Pressure on the next ball
        </h2>
        {reading ? (
          <>
            <p className="flex items-baseline gap-2">
              <span className="text-lg font-semibold">{pressureBand(reading.pressure)}</span>
              <span className="font-mono text-sm text-muted-foreground tabular-nums">
                {reading.pressure}/100
              </span>
            </p>
            <PressureMeter pressure={reading.pressure} />
            <p className="text-xs leading-relaxed text-muted-foreground">
              It can move the match{" "}
              <span className="font-mono text-foreground tabular-nums">
                {formatLeverage(reading.leverage)}
              </span>{" "}
              as much as a typical {c.label} ball.{" "}
              {competition === "ipl" && (
                <Link
                  href={competitionPath(competition, "/lab/pressure")}
                  className="text-foreground underline-offset-4 hover:underline"
                >
                  About pressure
                </Link>
              )}
            </p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">The innings is over.</p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-xs tracking-wide text-muted-foreground uppercase">
          Momentum, last 12 balls
        </h2>
        {momentum ? (
          (() => {
            const side = sideOf(momentum.inningsNo);
            const team = side === "a" ? team_a : team_b;
            const rounded = Math.round(momentum.points);
            return (
              <>
                <p className="flex items-baseline gap-2">
                  <span className="text-lg font-semibold">{team.franchise_id}</span>
                  <span className="font-mono text-sm tabular-nums">
                    {rounded === 0 ? "±0" : `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)}`} pts
                  </span>
                </p>
                <MomentumBar points={momentum.points} color={SIDE_COLORS[side]} />
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {team.name}&apos;s change in win probability over the last 12 balls. It describes
                  what just happened; it barely predicts what comes next.{" "}
                  {competition === "ipl" && (
                    <Link
                      href={competitionPath(competition, "/lab/momentum")}
                      className="text-foreground underline-offset-4 hover:underline"
                    >
                      The evidence
                    </Link>
                  )}
                </p>
              </>
            );
          })()
        ) : (
          <p className="text-sm text-muted-foreground">Starts with the first ball.</p>
        )}
      </div>
    </section>
  );
}
