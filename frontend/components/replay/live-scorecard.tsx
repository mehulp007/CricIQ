import Link from "next/link";

import { TeamSwatch } from "@/components/match/team-badge";
import type { Timeline } from "@/lib/api/types";
import { formatRate, oversNotation } from "@/lib/cricket";
import { formatScore, inningsLabel } from "@/lib/format";
import { type LiveInningsCard, playerName } from "@/lib/replay/engine";
import { cn } from "@/lib/utils";

const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
const td = "px-2 py-2 text-right font-mono tabular-nums";

function PlayerLink({ timeline, id }: { timeline: Timeline; id: string }) {
  return (
    <Link
      href={`/players/${id}`}
      className="underline-offset-4 hover:text-primary hover:underline"
      prefetch={false}
    >
      {playerName(timeline, id)}
    </Link>
  );
}

function InningsCard({ timeline, card }: { timeline: Timeline; card: LiveInningsCard }) {
  const team = timeline.teams[card.innings.batting_team_id];
  return (
    <section
      aria-label={`${team.name}, ${inningsLabel(card.innings.innings_no, card.innings.is_super_over)}`}
      className="rounded-2xl border border-border bg-card/70 p-5"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-2 font-medium">
          <TeamSwatch color={team.color} />
          {team.name}
          <span className="text-xs font-normal text-muted-foreground">
            {inningsLabel(card.innings.innings_no, card.innings.is_super_over)}
            {!card.complete && " · in progress"}
          </span>
        </h3>
        <p className="font-mono tabular-nums">
          <span className="text-lg font-semibold">{formatScore(card.runs, card.wickets)}</span>
          <span className="text-sm text-muted-foreground"> ({card.overs} ov)</span>
        </p>
      </header>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                Batter
              </th>
              <th scope="col" className={th}>
                R
              </th>
              <th scope="col" className={th}>
                B
              </th>
              <th scope="col" className={th}>
                4s
              </th>
              <th scope="col" className={th}>
                6s
              </th>
              <th scope="col" className={th}>
                SR
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {card.batting.map((b) => (
              <tr key={b.id}>
                <th scope="row" className="px-2 py-2 text-left font-normal">
                  <PlayerLink timeline={timeline} id={b.id} />
                  <span
                    className={cn(
                      "block text-xs",
                      b.isOut ? "text-muted-foreground" : "text-primary",
                    )}
                  >
                    {b.dismissal ?? "not out"}
                  </span>
                </th>
                <td className={cn(td, "font-semibold")}>{b.runs}</td>
                <td className={td}>{b.balls}</td>
                <td className={td}>{b.fours}</td>
                <td className={td}>{b.sixes}</td>
                <td className={cn(td, "text-muted-foreground")}>
                  {formatRate(b.balls ? (b.runs * 100) / b.balls : null)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="px-2 pt-2 text-xs text-muted-foreground">
          Extras <span className="font-mono text-foreground tabular-nums">{card.extras}</span>
        </p>
      </div>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={cn(th, "text-left")}>
                Bowler
              </th>
              <th scope="col" className={th}>
                O
              </th>
              <th scope="col" className={th}>
                M
              </th>
              <th scope="col" className={th}>
                R
              </th>
              <th scope="col" className={th}>
                W
              </th>
              <th scope="col" className={th}>
                Econ
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {card.bowling.map((b) => (
              <tr key={b.id}>
                <th scope="row" className="px-2 py-2 text-left font-normal">
                  <PlayerLink timeline={timeline} id={b.id} />
                </th>
                <td className={td}>{oversNotation(b.legalBalls)}</td>
                <td className={td}>{b.maidens}</td>
                <td className={td}>{b.runs}</td>
                <td className={cn(td, "font-semibold")}>{b.wickets}</td>
                <td className={cn(td, "text-muted-foreground")}>
                  {formatRate(b.legalBalls ? (b.runs * 6) / b.legalBalls : null)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function LiveScorecard({
  timeline,
  cards,
}: {
  timeline: Timeline;
  cards: LiveInningsCard[];
}) {
  if (cards.length === 0) {
    return (
      <p className="py-10 text-center text-muted-foreground">
        The scorecard fills in as the replay plays.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {cards.map((card) => (
        <InningsCard key={card.innings.innings_no} timeline={timeline} card={card} />
      ))}
    </div>
  );
}
