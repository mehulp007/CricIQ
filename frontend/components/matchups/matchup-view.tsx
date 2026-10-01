import Link from "next/link";

import { NextBallPanel } from "@/components/matchups/next-ball";
import { ReadingsChart, ReadingsLegend } from "@/components/matchups/readings-chart";
import { Panel, ParDelta, StatTile } from "@/components/players/profile-parts";
import type { MatchupDetail, MatchupPlayer } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { PHASE_OPTIONS, SAMPLE_LABELS, weightSentence } from "@/lib/matchups";
import { dismissalLabel, handLabel, rate } from "@/lib/players";
import { cn } from "@/lib/utils";
import { scrollRegion } from "@/lib/a11y";

const th = "px-2 py-2 text-right text-xs font-medium text-muted-foreground";
const td = "px-2 py-2.5 text-right font-mono tabular-nums";

function describe(player: MatchupPlayer, role: "batter" | "bowler"): string {
  if (role === "batter") return handLabel(player.batting_hand) ?? "Batter";
  return player.bowling_style ?? (player.bowling_type === "spin" ? "Spin" : "Pace");
}

function SampleBadge({ detail }: { detail: MatchupDetail }) {
  const { level, balls } = detail.sample;
  const tone =
    level === "large" || level === "moderate"
      ? "border-primary/40 text-primary"
      : "border-border text-muted-foreground";
  return (
    <span className={cn("rounded-full border px-2.5 py-0.5 text-xs", tone)}>
      {SAMPLE_LABELS[level]}
      {balls > 0 && ` · ${balls} balls`}
    </span>
  );
}

function PhaseFilter({ detail }: { detail: MatchupDetail }) {
  const base = `/matchups?batter=${detail.batter.player_id}&bowler=${detail.bowler.player_id}`;
  const options = [{ value: undefined, label: "All phases" }, ...PHASE_OPTIONS];
  return (
    <nav aria-label="Phase filter" className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const on = (detail.phase ?? undefined) === o.value;
        return (
          <Link
            key={o.label}
            href={o.value ? `${base}&phase=${o.value}` : base}
            aria-current={on ? "page" : undefined}
            scroll={false}
            className={cn(
              "inline-flex h-8 items-center rounded-lg border px-3 text-xs transition-colors",
              on
                ? "border-primary/50 bg-primary/10 text-foreground"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {o.label}
          </Link>
        );
      })}
    </nav>
  );
}

function SplitTable({ rows, caption }: { rows: MatchupDetail["by_phase"]; caption: string }) {
  return (
    <div className="overflow-x-auto" {...scrollRegion(caption)}>
      <table className="w-full min-w-[28rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b border-border">
          <tr>
            <th scope="col" className={cn(th, "text-left")}>
              Split
            </th>
            <th scope="col" className={th}>
              Balls
            </th>
            <th scope="col" className={th}>
              Runs
            </th>
            <th scope="col" className={th}>
              Outs
            </th>
            <th scope="col" className={th}>
              SR
            </th>
            <th scope="col" className={th}>
              <abbr title="Strike rate the model expects from the two players' overall records">
                Expected
              </abbr>
            </th>
            <th scope="col" className={th}>
              Diff
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={r.key} className={cn(r.balls < 30 && "text-muted-foreground")}>
              <th scope="row" className="px-2 py-2.5 text-left font-normal">
                {r.label}
              </th>
              <td className={cn(td, "text-muted-foreground")}>{r.balls}</td>
              <td className={td}>{r.runs}</td>
              <td className={td}>{r.dismissals}</td>
              <td className={cn(td, "font-semibold")}>{rate(r.strike_rate, 1)}</td>
              <td className={cn(td, "text-muted-foreground")}>{rate(r.expected_strike_rate, 1)}</td>
              <td className={td}>
                <ParDelta
                  delta={
                    r.strike_rate !== null && r.expected_strike_rate !== null
                      ? r.strike_rate - r.expected_strike_rate
                      : null
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MatchupView({ detail }: { detail: MatchupDetail }) {
  const { batter, bowler, head_to_head: h2h } = detail;
  const hasHistory = h2h.balls > 0;
  const phaseLabel = PHASE_OPTIONS.find((p) => p.value === detail.phase)?.label.toLowerCase();
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h2 className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-2xl font-semibold tracking-tight">
          <Link href={`/players/${batter.player_id}`} className="hover:text-primary">
            {batter.full_name ?? batter.name}
          </Link>
          <span className="text-base font-normal text-muted-foreground">vs</span>
          <Link href={`/players/${bowler.player_id}`} className="hover:text-primary">
            {bowler.full_name ?? bowler.name}
          </Link>
        </h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
          <SampleBadge detail={detail} />
          <span>
            {describe(batter, "batter")} vs {describe(bowler, "bowler").toLowerCase()}
          </span>
          <span>
            {detail.window.first}–{detail.window.last}
            {phaseLabel && ` · ${phaseLabel}`}
          </span>
        </div>
        <PhaseFilter detail={detail} />
      </header>

      {hasHistory ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile label="Balls" value={h2h.balls}>
              {h2h.runs} runs · {h2h.dots} dots · {h2h.fours} fours · {h2h.sixes} sixes
            </StatTile>
            <StatTile label="Dismissals" value={h2h.dismissals}>
              {h2h.average !== null && h2h.average !== undefined
                ? `Average ${h2h.average.toFixed(1)} runs per dismissal`
                : "Never dismissed by this bowler"}
            </StatTile>
            <StatTile label="Strike rate" value={rate(detail.raw?.strike_rate.value, 1)}>
              Expected {rate(detail.expected?.strike_rate.value, 1)} from overall form
            </StatTile>
            <StatTile label="CricIQ estimate" value={rate(detail.estimate?.strike_rate.value, 1)}>
              Strike rate, shrunk towards the expectation · {Math.round(detail.sample.weight * 100)}
              % head-to-head
            </StatTile>
          </div>

          <Panel
            id="readings"
            title="Three ways to read the record"
            lede={weightSentence(detail.sample.weight, detail.sample.kappa)}
          >
            <div className="flex flex-col gap-5">
              <ReadingsLegend />
              <ReadingsChart detail={detail} />
              <p className="text-xs leading-relaxed text-muted-foreground">
                Bars are 90% intervals. The head-to-head interval shows how little a few dozen balls
                prove; the estimate is narrower because it also leans on everything else both
                players have done. Expected is what the ball-outcome model predicts for these same
                balls without any head-to-head knowledge.
              </p>
            </div>
          </Panel>
        </>
      ) : (
        <p className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
          {batter.full_name ?? batter.name} has not faced {bowler.full_name ?? bowler.name}
          {phaseLabel ? ` in the ${phaseLabel}` : ""} in these seasons. The next-ball odds below
          come from their overall records alone.
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel
          id="next-ball"
          title="Next ball"
          lede="The chance of each outcome on the next ball this batter faces from this bowler."
        >
          <NextBallPanel
            balls={detail.next_ball}
            hasHistory={hasHistory}
            context={detail.context}
          />
        </Panel>
        {hasHistory && (
          <div className="flex flex-col gap-6">
            <Panel id="matchup-phases" title="By phase">
              <SplitTable rows={detail.by_phase} caption="Head-to-head by phase" />
            </Panel>
            <Panel id="matchup-dismissals" title="Dismissals">
              {detail.dismissals.length ? (
                <ul className="divide-y divide-border text-sm">
                  {detail.dismissals.map((d, i) => (
                    <li key={`${d.match_id}-${i}`} className="flex justify-between gap-3 py-2">
                      <Link
                        href={`/matches/${d.match_id}`}
                        className="underline-offset-4 hover:text-primary hover:underline"
                      >
                        {formatDate(d.date)}
                      </Link>
                      <span className="text-muted-foreground">{dismissalLabel(d.kind)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {bowler.full_name ?? bowler.name} has never dismissed{" "}
                  {batter.full_name ?? batter.name} here.
                </p>
              )}
            </Panel>
          </div>
        )}
      </div>

      {detail.by_season.length > 1 && (
        <Panel id="matchup-seasons" title="By season">
          <SplitTable rows={detail.by_season} caption="Head-to-head by season" />
        </Panel>
      )}
    </div>
  );
}
