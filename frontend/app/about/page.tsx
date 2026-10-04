import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DATA_VERSION } from "@/lib/featured";
import { BALL_OUTCOME, RATINGS, SCORE_PROJECTION, WIN_PROBABILITY, seasonSpan } from "@/lib/models";

export const metadata: Metadata = {
  title: "About & Methodology",
  description:
    "How CricIQ is built: data sources and validation, the win probability, score projection and ball-outcome models, par, win probability added, CricIQ Ratings, similar players, matchup shrinkage and limitations.",
};

const PRINCIPLES: { title: string; body: string }[] = [
  {
    title: "No peeking into the future",
    body: "Every player, venue and form feature is computed only from matches played before the moment being analysed. Models are trained on older seasons and tested once on the most recent ones.",
  },
  {
    title: "Calibrated, not just accurate",
    body: "A 70% win probability should come true about 70% of the time. Models are judged on log loss, Brier score and calibration, never on accuracy alone.",
  },
  {
    title: "Honest about sample size",
    body: "Small samples are shown with their size and shrunk toward sensible baselines, with intervals, instead of being presented as certainties.",
  },
  {
    title: "Estimates, not guarantees",
    body: "Every prediction is a statistical estimate from historical data. CricIQ is a sports analytics project and is not intended for betting.",
  },
];

function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="text-xl font-semibold tracking-tight">
        {title}
      </h2>
      <div className="flex flex-col gap-3 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

function A({ href, children }: { href: string; children: ReactNode }) {
  const external = href.startsWith("http");
  return external ? (
    <a
      href={href}
      className="text-primary underline-offset-4 hover:underline"
      target="_blank"
      rel="noreferrer"
    >
      {children}
    </a>
  ) : (
    <Link href={href} className="text-primary underline-offset-4 hover:underline">
      {children}
    </Link>
  );
}

function Strong({ children }: { children: ReactNode }) {
  return <span className="font-medium text-foreground">{children}</span>;
}

export default function AboutPage() {
  const wp = WIN_PROBABILITY.test;
  const sp = SCORE_PROJECTION.test;
  const bo = BALL_OUTCOME.test;
  const boGain = (bo.baseline.log_loss - bo.model.log_loss) / bo.baseline.log_loss;
  const kappa = Math.round(BALL_OUTCOME.kappa);
  const economy = RATINGS.components.find((c) => c.role === "bowling" && c.key === "economy");
  const wickets = RATINGS.components.find((c) => c.role === "bowling" && c.key === "wickets");
  const scoring = RATINGS.components.find((c) => c.role === "batting" && c.key === "scoring");
  const low = RATINGS.components.filter((c) => c.stability === "low");

  return (
    <div className="flex max-w-3xl flex-col gap-12">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">About &amp; Methodology</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          CricIQ is a full-stack cricket analytics platform. It takes every IPL ball since 2008 from
          raw records through data engineering, leak-free feature engineering, tested machine
          learning and explainability, all the way to this interface. This page explains how each
          number on the site is made, and where it falls short.
        </p>
      </header>

      <section aria-labelledby="principles" className="flex flex-col gap-4">
        <h2 id="principles" className="text-xl font-semibold tracking-tight">
          Principles
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {PRINCIPLES.map((p) => (
            <Card key={p.title} className="bg-card/70">
              <CardHeader>
                <CardTitle className="text-base">{p.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm leading-relaxed text-muted-foreground">
                {p.body}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <Section id="data" title="The data">
        <p>
          Every IPL match is ingested ball by ball from{" "}
          <A href="https://cricsheet.org">Cricsheet</A>, normalised into a DuckDB warehouse and
          validated before anything downstream sees it: invariant checks (legal balls per over,
          wickets, targets, every team and venue mapped) and golden scorecards that must match known
          results exactly, such as the 2019 final and the rain-reduced 2023 final. A failed check
          stops the build, so invalid data never ships.
        </p>
        <p>
          Player names come from Cricsheet&apos;s register, never fuzzy matching. Batting hand and
          bowling style come from Wikidata and Wikipedia, with documented overrides. The current
          dataset is version <span className="font-mono text-foreground">{DATA_VERSION}</span>.
        </p>
      </Section>

      <Section id="models" title="The models">
        <p>
          <Strong>Win probability.</Strong> Two gradient-boosted tree models (first innings and
          chase) with monotonic constraints, so more runs or fewer wickets never lower a side&apos;s
          chance. A dynamic programme of the chase from recent death-over rates feeds the second
          innings. Tested once on {wp.matches} matches from{" "}
          {seasonSpan(WIN_PROBABILITY.splits.test)}: log loss {wp.model.log_loss.toFixed(3)} against{" "}
          {wp.baseline.log_loss.toFixed(3)} for a logistic baseline. Explanations are TreeSHAP
          contributions grouped into the situation, wickets and recent overs.
        </p>
        <p>
          <Strong>Score projection.</Strong> Quantile models of the runs still to come, measured
          against the scoring era so one model spans 2008 to today, then conformally calibrated
          level by level. On the test seasons the 80% range covered {pct(sp.model.coverage80)} of
          first-innings totals, and the median was off by {sp.model.mae.toFixed(1)} runs against{" "}
          {sp.par_baseline.mae.toFixed(1)} for par.
        </p>
        <p>
          <Strong>Ball outcome.</Strong> A multinomial logistic regression for the next ball: dot,
          1, 2, 3, 4, 6 or wicket, from the situation, the scoring era and a penalised effect for
          every batter and bowler. It is {pct(boGain, 2)} better than outcome frequencies by phase
          and wickets on log loss; single balls are noisy, so gains are small for any model. It is
          served as a table of additive terms, so the API computes it with plain arithmetic.
        </p>
        <p>
          Each model is tuned on one set of seasons, tested once on the latest, backtested season by
          season, and promoted only if it beats its baseline. The full protocols, results and
          rejected ideas are on <A href="/models">Model Insights</A>.
        </p>
      </Section>

      <Section id="player-metrics" title="Player Lab: par and win probability added">
        <p>
          <Strong>Par</Strong> is what an average IPL player would have produced from the same
          balls: the league rate for each ball&apos;s season and phase, summed over the
          player&apos;s balls. A strike rate of 135 meant more in 2010 than in 2025, and more in the
          powerplay than at the death; comparing with par removes both effects. Summed over every
          player, par reproduces the league exactly.
        </p>
        <p>
          <Strong>Percentiles</Strong> rank each measure against par among players with at least 300
          balls in the chosen seasons (120 within a phase). <Strong>Win probability added</Strong>{" "}
          credits every ball&apos;s change in the batting side&apos;s chance of winning to the
          batter and, negated, to the bowler; summed over a career it is roughly wins added.
        </p>
        <p>
          Par adjusts for season and phase only, not venue, match situation or opposition quality,
          and at the death it includes tailenders, which flatters top-order batters a little.
        </p>
      </Section>

      <Section id="ratings" title="CricIQ Ratings: honest about sample size">
        <p>
          A rating places a player among the regulars of the same seasons (
          {RATINGS.thresholds.min_balls}+ balls in the role) on one thing they do: run scoring,
          survival, each phase, chasing, impact and consistency for batters; economy, wicket-taking,
          each phase, defending, impact and consistency for bowlers. Every measure is against par,
          and there is deliberately no single overall number.
        </p>
        <p>
          Before ranking, each record is blended with the average:{" "}
          <span className="font-mono text-foreground">
            estimate = (own evidence + k × average) ÷ (own balls + k)
          </span>
          . The constant <Strong>k</Strong> is fitted per measure so a season&apos;s blended record
          best predicts the player&apos;s next season. A batter&apos;s strike rate against par needs
          about {Math.round(scoring?.k ?? 0)} balls before it counts for half the estimate; a
          bowler&apos;s economy needs {Math.round(economy?.k ?? 0)}, but wickets against par need{" "}
          {Math.round(wickets?.k ?? 0).toLocaleString("en-IN")}, because over a season they are
          mostly luck. The rating is the share of qualified players with a lower estimate, shown
          with a 90% interval.
        </p>
        <p>
          Some ratings barely carry over from one season to the next (
          {low.map((c) => `${c.role} ${c.label.toLowerCase()}`).join(", ")}); they are marked{" "}
          <Strong>low stability</Strong>. The full evaluation is on{" "}
          <A href="/models">Model Insights</A>.
        </p>
        <p>
          <Strong>Similar players</Strong> compares style profiles: per-ball rates against par
          (scoring, boundaries, dots, dismissals, or runs conceded) and how a player is used
          (phases, batting position, workload, pace or spin), standardised within the same seasons.
          From one season&apos;s profile, the same bowler is among the five closest next season{" "}
          {Math.round(100 * RATINGS.similarity.bowling.top5)}% of the time, against{" "}
          {Math.round(100 * RATINGS.similarity.bowling.chance_top5)}% by chance.
        </p>
      </Section>

      <Section id="matchups" title="Matchup Lab: three readings of a record">
        <p>
          Even the longest IPL rivalry is only about 160 balls, and the median pair has met for 5.
          Every head-to-head record is therefore shown three ways: what happened, what the
          ball-outcome model expects for those same balls from each player&apos;s overall record,
          and an estimate that blends the two.
        </p>
        <p>
          The blend is empirical Bayes: a Dirichlet prior centred on the expectation, worth {kappa}{" "}
          balls, fitted across every pair. The record gets weight balls ÷ (balls + {kappa}), so a
          30-ball history carries about {Math.round((30 / (30 + kappa)) * 100)}% of the estimate. On
          later seasons, raw head-to-head rates predicted a pair&apos;s future balls far worse than
          the model; the shrunk records matched it. Intervals are 90%.
        </p>
      </Section>

      <Section id="engineering" title="How it is built">
        <p>
          A modular monolith in one repository: a Python data pipeline and ML package, a FastAPI
          service that reads a read-only DuckDB file baked into its image, and this Next.js app.
          Everything historical is precomputed when the API image is built: every ball&apos;s win
          probability, explanation and projection, and the player and matchup tables. The API never
          retrains; model versions are reviewed, committed and gated.
        </p>
        <p>
          Every change runs linting, type checks, Python and frontend unit tests, a build of the API
          image from live data with a smoke test, and end-to-end tests on desktop and mobile,
          including an automated accessibility scan of every key page. Featured replays and model
          insights are bundled with the site, so they load instantly even when the free-tier API is
          asleep.
        </p>
      </Section>

      <Section id="limitations" title="Limitations">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            No ball tracking: line, length, pace, field settings and shot direction are not in the
            data.
          </li>
          <li>
            No pitch, weather, dew or team news. Venue enters only through what happened there.
          </li>
          <li>
            New matches appear after the data is refreshed and redeployed; the models are retrained
            deliberately, not automatically.
          </li>
          <li>
            Scoring keeps rising. Models adjust for the era as it happens, but run slightly behind a
            sudden jump, as in the Impact Player seasons.
          </li>
          <li>
            Pre-match predictions and match simulation are not offered yet: before a ball is bowled,
            a T20 match is close to a coin flip.
          </li>
        </ul>
      </Section>

      <Section id="attribution" title="Data &amp; attribution">
        <p>
          Ball-by-ball data is from <A href="https://cricsheet.org">Cricsheet</A>, used under the{" "}
          <A href="https://opendatacommons.org/licenses/by/1-0/">
            Open Data Commons Attribution License
          </A>
          . Player attributes come from <A href="https://www.wikidata.org">Wikidata</A> (CC0) and
          English <A href="https://en.wikipedia.org">Wikipedia</A> infoboxes (
          <A href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</A>).
        </p>
        <p>
          CricIQ is an independent portfolio project. It is not affiliated with, endorsed by, or
          connected to the Indian Premier League, the BCCI or any franchise. Team names and colours
          are used only to describe historical matches; no logos are used.
        </p>
      </Section>
    </div>
  );
}
