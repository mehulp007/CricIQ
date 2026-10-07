import Link from "next/link";

import { Section, Stat } from "@/components/models/section";
import { Badge } from "@/components/ui/badge";
import { scrollRegion } from "@/lib/a11y";
import { competitionPath, type CompetitionId } from "@/lib/competitions";
import {
  RATINGS,
  type RatingComponentEvaluation,
  type RatingsInsights as Insights,
  seasonSpan,
} from "@/lib/models";
import { cn } from "@/lib/utils";

const STABILITY = {
  high: "High",
  moderate: "Moderate",
  low: "Low",
} as const;

function pct(value: number | undefined, digits = 0): string {
  if (value === undefined) return "—";
  const text = Math.abs(100 * value).toFixed(digits);
  return `${value >= 0 ? "+" : "−"}${text}%`;
}

function weight(c: RatingComponentEvaluation): string {
  const size = c.exposure === "balls" ? "300" : "30";
  return `${Math.round(100 * c.weight_at[size])}% at ${size} ${c.exposure}`;
}

/** Year-to-year correlation as a bar on 0-0.7, with the stability thresholds marked. */
function Persistence({ c, ri }: { c: RatingComponentEvaluation; ri: Insights }) {
  const r = c.year_to_year.r;
  const scale = 0.7;
  return (
    <span className="flex items-center gap-2">
      <span
        className="relative h-2 w-24 rounded-full bg-muted"
        role="img"
        aria-label={`Year-to-year correlation ${r === null ? "not available" : r.toFixed(2)}`}
      >
        {r !== null && (
          <span
            aria-hidden="true"
            className="absolute inset-y-0 left-0 rounded-full"
            style={{
              width: `${Math.min(Math.max(r, 0) / scale, 1) * 100}%`,
              background: "var(--chart-3)",
            }}
          />
        )}
        {[ri.stability.moderate, ri.stability.high].map((t) => (
          <span
            key={t}
            aria-hidden="true"
            className="absolute -inset-y-0.5 w-px bg-foreground/40"
            style={{ left: `${(t / scale) * 100}%` }}
          />
        ))}
      </span>
      <span className="w-9 font-mono tabular-nums">{r === null ? "—" : r.toFixed(2)}</span>
    </span>
  );
}

function ComponentTable({ role, ri }: { role: "batting" | "bowling"; ri: Insights }) {
  const rows = ri.components.filter((c) => c.role === role);
  return (
    <div className="overflow-x-auto" {...scrollRegion(`${role} rating components`)}>
      <table className="w-full min-w-3xl text-sm">
        <thead className="text-left text-xs text-muted-foreground">
          <tr className="border-b border-border">
            <th className="py-2 pr-3 font-medium">Component</th>
            <th className="py-2 pr-3 text-right font-medium">
              <abbr title="Balls or innings of the average blended into every record">k</abbr>
            </th>
            <th className="py-2 pr-3 text-right font-medium">Own record counts</th>
            <th className="py-2 pr-3 font-medium">Year to year</th>
            <th className="py-2 pr-3 text-right font-medium">
              <abbr title="Correlation between a player's records in odd and in even seasons">
                Odd/even seasons
              </abbr>
            </th>
            <th className="py-2 pr-3 text-right font-medium">
              <abbr title="Cut in squared error predicting the next season, against par and against the raw record">
                Next season vs par / raw
              </abbr>
            </th>
            <th className="py-2 text-right font-medium">Stability</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((c) => (
            <tr key={c.key}>
              <th scope="row" className="py-2.5 pr-3 text-left font-normal">
                {c.label}
                <span className="block text-xs text-muted-foreground">{c.unit_label}</span>
              </th>
              <td className="py-2.5 pr-3 text-right font-mono tabular-nums">
                {Math.round(c.k).toLocaleString("en-IN")}
              </td>
              <td className="py-2.5 pr-3 text-right text-xs text-muted-foreground">{weight(c)}</td>
              <td className="py-2.5 pr-3">
                <Persistence c={c} ri={ri} />
              </td>
              <td className="py-2.5 pr-3 text-right font-mono text-muted-foreground tabular-nums">
                {c.split_half.r === null ? "—" : c.split_half.r.toFixed(2)}
              </td>
              <td className="py-2.5 pr-3 text-right font-mono tabular-nums">
                {pct(c.next_season.skill_vs_par, 1)}
                <span className="text-muted-foreground"> / {pct(c.next_season.skill_vs_raw)}</span>
              </td>
              <td className="py-2.5 text-right">
                <span
                  className={cn(
                    "text-xs",
                    c.stability === "low" ? "text-muted-foreground" : "text-foreground",
                  )}
                >
                  {STABILITY[c.stability]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Retrieval({ role, ri }: { role: "batting" | "bowling"; ri: Insights }) {
  const s = ri.similarity[role];
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-3 gap-3 text-center">
        {(
          [
            ["Closest", s.top1, s.chance_top1],
            ["Top five", s.top5, s.chance_top5],
          ] as const
        ).map(([label, value, chance]) => (
          <div key={label} className="rounded-xl bg-muted/40 px-2 py-3">
            <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</dt>
            <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">
              {Math.round(100 * value)}%
            </dd>
            <dd className="text-[11px] text-muted-foreground">
              chance {Math.round(100 * chance)}%
            </dd>
          </div>
        ))}
        <div className="rounded-xl bg-muted/40 px-2 py-3">
          <dt className="text-[11px] tracking-wide text-muted-foreground uppercase">Median rank</dt>
          <dd className="mt-1 font-mono text-xl font-semibold tabular-nums">{s.median_rank}</dd>
          <dd className="text-[11px] text-muted-foreground">of {s.candidates_median}</dd>
        </div>
      </dl>
      <p className="text-xs leading-relaxed text-muted-foreground">
        {s.players} player-seasons. Profile:{" "}
        {s.features.map((f) => f.label.toLowerCase()).join(", ")}.
      </p>
    </div>
  );
}

export function RatingsInsights({
  data: ri = RATINGS,
  competition = "ipl",
}: {
  data?: Insights;
  competition?: CompetitionId;
}) {
  const components = ri.components;
  const beatsRaw = components.filter((c) => (c.next_season.skill_vs_raw ?? 0) > 0).length;
  const high = components.filter((c) => c.stability === "high");
  const wickets = components.find((c) => c.role === "bowling" && c.key === "wickets");
  const economy = components.find((c) => c.role === "bowling" && c.key === "economy");
  const t = ri.thresholds;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="font-mono text-[11px] text-primary">
            Ratings v{ri.version}
          </Badge>
          <Badge variant="outline" className="font-mono text-[11px] text-muted-foreground">
            Fitted on {seasonSpan(ri.trained_on.seasons)}
          </Badge>
        </div>
        <p className="max-w-3xl leading-relaxed text-muted-foreground">
          CricIQ Ratings place a player among the regulars of the same seasons on each thing they
          do, from 0 to 100, after blending their record with the average according to how much a
          record of that size can be trusted. They appear on every{" "}
          <Link
            href={competitionPath(competition, "/players")}
            className="text-foreground underline-offset-4 hover:underline"
          >
            player profile
          </Link>{" "}
          and in{" "}
          <Link
            href={competitionPath(competition, "/compare")}
            className="text-foreground underline-offset-4 hover:underline"
          >
            Compare
          </Link>
          . This tab shows how far each kind of record can be trusted, and which ones persist.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Shrinking helps"
          value={`${beatsRaw} of ${components.length}`}
          context={`Components where the shrunk record predicts a player's next season better than the raw record (seasons from ${ri.splits.test_from}).`}
        />
        <Stat
          label="Persistent skills"
          value={String(high.length)}
          context={`Ratings that correlate at least ${ri.stability.high} from one season to the next: ${high.map((c) => `${c.role} ${c.label.toLowerCase()}`).join(", ")}.`}
        />
        <Stat
          label="Economy vs wickets"
          value={`${Math.round(economy?.k ?? 0)} vs ${Math.round(wickets?.k ?? 0).toLocaleString("en-IN")}`}
          context="Balls of the average blended in: an economy record is trusted quickly, a wicket record against par barely at all."
        />
        <Stat
          label="Similar players"
          value={`${Math.round(100 * ri.similarity.bowling.top5)}%`}
          context={`How often a bowler's profile finds the same bowler in next season's top five (chance ${Math.round(100 * ri.similarity.bowling.chance_top5)}%).`}
        />
      </div>

      <Section
        id="ratings-batting-heading"
        title="Batting: which records can be trusted?"
        lede={`k is the number of balls (or innings) of the average blended into every record, tuned so a season's shrunk record best predicts the next. "Year to year" correlates players' single-season ratings; ticks mark ${ri.stability.moderate} and ${ri.stability.high}.`}
      >
        <ComponentTable role="batting" ri={ri} />
      </Section>

      <Section
        id="ratings-bowling-heading"
        title="Bowling: runs conceded tell you more than wickets"
        lede="Economy against par settles quickly and carries over; wickets against par are mostly the luck of when chances are taken, so the record needs thousands of balls before it outweighs the average."
      >
        <ComponentTable role="bowling" ri={ri} />
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section
          id="ratings-similar-heading"
          title="Do style profiles identify a player?"
          lede={`From a player's style in one season, how often is the most similar profile among next season's players the same player? Season windows, ${t.style_min_balls}+ balls in both seasons.`}
        >
          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            {(["batting", "bowling"] as const).map((role) => (
              <div key={role} className="flex flex-col gap-2">
                <h3 className="text-sm font-medium">
                  {role === "batting" ? "Batters" : "Bowlers"}
                </h3>
                <Retrieval role={role} ri={ri} />
              </div>
            ))}
          </div>
        </Section>

        <Section
          id="ratings-method-heading"
          title="How it works"
          lede="Records against par, shrunk by empirical Bayes, ranked among regulars."
        >
          <ul className="flex flex-col gap-3 text-sm leading-relaxed text-muted-foreground">
            <li>
              <span className="font-medium text-foreground">Evidence.</span> Each component sums
              what a player did beyond par, innings by innings: runs above par, dismissals avoided,
              runs saved, win probability added, or innings at par or better.
            </li>
            <li>
              <span className="font-medium text-foreground">Shrinkage.</span> The estimate is (own
              evidence + k × average) ÷ (own balls + k), towards the average of qualified players (
              {t.min_balls}+ balls) in the same seasons.
            </li>
            <li>
              <span className="font-medium text-foreground">Rating.</span> The share of qualified
              players with a lower estimate. The 90% interval comes from the noise per ball,
              measured from how much a player&apos;s innings vary within a season.
            </li>
            <li>
              <span className="font-medium text-foreground">Similar players.</span> Per-ball rates
              against par and usage shares, z-scored within the window; similarity is the cosine
              between two profiles.
            </li>
          </ul>
        </Section>
      </div>
    </div>
  );
}
