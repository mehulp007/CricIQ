import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import {
  ProjectionBacktestChart,
  ReliabilityChart,
  SeriesLegend,
} from "@/components/models/charts";
import { CLUTCH, MOMENTUM, PRESSURE } from "@/lib/lab";
import {
  BALL_OUTCOME,
  RATINGS,
  SCORE_PROJECTION,
  SIMULATOR,
  WIN_PROBABILITY,
  favouriteAccuracy,
  seasonSpan,
} from "@/lib/models";

export const metadata: Metadata = {
  title: "Building CricIQ",
  description:
    "What 295,732 IPL balls can and can't tell you: how CricIQ's win probability, score projection, matchups, ratings, pressure and match simulator were built, tested on seasons they never saw, and shipped for free.",
};

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <h2 id={id} className="text-2xl font-semibold tracking-tight">
        {title}
      </h2>
      <div className="flex flex-col gap-4 text-[15px] leading-7 text-muted-foreground">
        {children}
      </div>
    </section>
  );
}

function A({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="text-primary underline-offset-4 hover:underline">
      {children}
    </Link>
  );
}

function Strong({ children }: { children: ReactNode }) {
  return <strong className="font-medium text-foreground">{children}</strong>;
}

function Figure({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <figure className="flex flex-col gap-3 rounded-2xl border border-border bg-card/70 p-4 sm:p-5">
      {children}
      <figcaption className="text-xs leading-relaxed text-muted-foreground">{caption}</figcaption>
    </figure>
  );
}

function PullQuote({ children }: { children: ReactNode }) {
  return (
    <blockquote className="border-l-2 border-primary pl-4 text-lg leading-8 text-foreground">
      {children}
    </blockquote>
  );
}

export default function WriteupPage() {
  const wp = WIN_PROBABILITY.test;
  const sp = SCORE_PROJECTION.test;
  const bo = BALL_OUTCOME.test;
  const sim = SIMULATOR;
  const tested = seasonSpan(WIN_PROBABILITY.splits.test);
  const accuracy = favouriteAccuracy(wp.reliability);
  const ballGain = 1 - bo.model.log_loss / bo.baseline.log_loss;
  const history = BALL_OUTCOME.matchups.all;
  const tense = PRESSURE.swing_check[PRESSURE.swing_check.length - 1];
  const clutch = CLUTCH.roles.batting.split_half_r;
  const death = sp.by_phase.find((r) => r.phase === "death");
  const powerplay = sp.by_phase.find((r) => r.phase === "powerplay");
  const wpSeasons = WIN_PROBABILITY.backtest.filter(
    (r) => r.model_log_loss < r.baseline_log_loss,
  ).length;

  return (
    <article className="flex max-w-3xl flex-col gap-12">
      <header className="flex flex-col gap-4">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          The write-up · October 2026 · about 12 minutes
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Building CricIQ</h1>
        <p className="text-lg leading-8 text-muted-foreground">
          What 295,732 IPL balls can and can&apos;t tell you, and how to build a cricket analytics
          product that says which is which.
        </p>
        <p className="text-sm text-muted-foreground">By Mehul Patil</p>
      </header>

      <Section id="short" title="The short version">
        <p>
          CricIQ turns every IPL delivery since 2008 into something you can explore: replay any
          match ball by ball with each side&apos;s chance of winning, see a projected total with an
          honest range, read any batter against any bowler without over-reading five balls of
          history, rate players, feel the pressure on every ball, rebuild any season&apos;s table,
          and play any two sides from any season 10,000 times.
        </p>
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <Strong>Calibrated beats clever.</Strong> The win probability model is right about which
            side wins after {pct(accuracy)} of balls in {tested}, but the number that matters is
            that its 70% means 70%.
          </li>
          <li>
            <Strong>Most of cricket is noise.</Strong> The best ball-by-ball model is only{" "}
            {pct(ballGain, 1)} sharper than league averages, and before a ball is bowled a T20 match
            is a coin flip.
          </li>
          <li>
            <Strong>Say no out loud.</Strong> Player, venue and squad features, momentum and clutch
            all failed their tests. Each failure is on the site.
          </li>
          <li>
            <Strong>Precompute the past, compute only the questions.</Strong> Every real ball is
            scored at build time; only simulations and what-ifs run live, on free hosting.
          </li>
        </ul>
      </Section>

      <Section id="data" title="1,243 matches, not 295,732 rows">
        <p>
          The data is <A href="https://cricsheet.org">Cricsheet</A>&apos;s ball-by-ball record of
          every IPL match: 19 seasons, 1,243 matches and 295,732 deliveries. It looks like a big
          dataset. It is not. Every ball in a match shares one result, so for anything about winning
          the honest sample size is about 1,200 matches. That one fact shaped everything: models
          stay small, data is split by season and never by ball, and every uncertainty interval
          resamples whole matches.
        </p>
        <p>
          The second fact is drift. Average first-innings totals rose by about 27 runs once the
          Impact Player rule arrived in 2023. A model trained on 2008 to 2022 that knows nothing
          about this under-projects every modern innings. So every model gets an as-of &quot;scoring
          era&quot; feature (league runs per ball over the previous 60 matches) and is always tested
          on the most recent seasons, the hardest ones.
        </p>
        <p>
          Before any of that, the data is checked: 17 invariants (legal balls per over, wickets,
          targets, rain-revised chases), 6 golden scorecards and, since the Teams milestone, all 19
          official league tables, which must match to the third decimal of net run rate or the build
          fails.
        </p>
      </Section>

      <Section id="win-probability" title="A win probability you can trust">
        <p>
          The heart of the replay is each side&apos;s chance of winning after every ball: two
          gradient-boosted models (first innings and chase) with monotonic constraints, so more runs
          or more wickets in hand can never make a side less likely to win. Tested once on the{" "}
          {wp.matches} matches of {tested}, it reaches a log loss of {wp.model.log_loss.toFixed(3)}{" "}
          against {wp.baseline.log_loss.toFixed(3)} for logistic regression on the match state, and
          beats that baseline in {wpSeasons} of {WIN_PROBABILITY.backtest.length} backtest seasons.
        </p>
        <Figure
          caption={`Does 70% mean 70%? Predicted chance against how often it happened, on every ball of ${tested}. Points on the diagonal are perfectly calibrated.`}
        >
          <SeriesLegend />
          <ReliabilityChart model={wp.reliability} baseline={wp.baseline_reliability} />
        </Figure>
        <p>
          The more interesting results are the ones that did not make it. I built as-of player
          quality, venue history and squad strength, all leak-free, and tested each season by
          season. None improved on the match state plus the scoring era, so none is used. A leakage
          test backs the &quot;leak-free&quot;: it rewrites every match after a given one and checks
          that no earlier feature moves.
        </p>
        <p>
          Every swing is explained in cricket terms, from grouped TreeSHAP contributions (&quot;+7
          wickets in hand&quot;, &quot;required rate climbing&quot;), and near the end of a chase,
          where data is thinnest, an exact dynamic programme over runs, balls and wickets takes
          over.
        </p>
      </Section>

      <Section id="projection" title="Ranges that mean what they say">
        <p>
          A projected total is easy; an honest range is not. CricIQ predicts quantiles of the final
          first-innings total relative to the scoring era, then shifts them with conformal
          calibration on held-out seasons. On {tested} the 80% range held{" "}
          <Strong>{pct(sp.model.coverage80)}</Strong> of totals, and the median missed by{" "}
          {sp.model.mae.toFixed(1)} runs (par: {sp.par_baseline.mae.toFixed(1)}; the TV-style
          run-rate projection: {sp.run_rate.mae.toFixed(1)}).
          {death && powerplay
            ? ` The miss shrinks from ${Math.round(powerplay.model_mae)} runs in the powerplay to ${Math.round(death.model_mae)} at the death.`
            : ""}
        </p>
        <Figure caption="Median error of the projection by season against par for the era: it stays ahead as scoring rose by 30 runs.">
          <SeriesLegend baseline="Par for the era" />
          <ProjectionBacktestChart rows={SCORE_PROJECTION.backtest} />
        </Figure>
      </Section>

      <Section id="matchups" title="Five balls is not a rivalry">
        <p>
          The median batter-bowler pair in IPL history has met for five balls. Raw head-to-head
          records are mostly noise, so the Matchup Lab treats them the way a careful scout would. A
          ball-outcome model (a penalised multinomial regression over dot, 1, 2, 3, 4, 6 and wicket)
          says what each player&apos;s overall record expects, and each pair&apos;s history is
          blended with that expectation. How much to trust history is fitted across all pairs by
          empirical Bayes: history earns weight like{" "}
          {Math.round(BALL_OUTCOME.matchups.served_kappa)} balls of evidence would.
        </p>
        <PullQuote>
          On {history.balls.toLocaleString("en-IN")} test balls between pairs who had met before,
          raw head-to-head rates scored a log loss of {history.raw.toFixed(3)}; the model alone,{" "}
          {history.model.toFixed(3)}.
        </PullQuote>
        <p>
          The same model powers next-ball odds and the simulator. It is served as a table of
          additive terms, so the API computes odds with plain arithmetic and no machine-learning
          library at runtime.
        </p>
      </Section>

      <Section id="ratings" title="Par, ratings, and how much to trust a record">
        <p>
          A strike rate of 135 meant something different in 2010 than in 2025, and in the powerplay
          than at the death. Every Player Lab number comes with <Strong>par</Strong>: what an
          average IPL player would have produced from the same balls. Summed over all players, par
          reproduces the league exactly, a tested invariant.
        </p>
        <p>
          CricIQ Ratings then rank players among the regulars of the same seasons on{" "}
          {RATINGS.components.length} separate skills, each record blended with the average by how
          much a sample of that size can be trusted. The fitted trust is revealing: a batter&apos;s
          strike rate is half signal after about 460 balls, a bowler&apos;s economy after about 320,
          but <Strong>wickets need about 3,800</Strong>. Over a season, wickets are mostly luck;
          runs conceded say more about a bowler. There is deliberately no single overall number.
        </p>
      </Section>

      <Section id="lab" title="Testing ideas that could fail">
        <p>The Analytics Lab exists for ideas that sound true. Each got a test it could fail.</p>
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <Strong>Pressure works.</Strong> Leverage (how far the next ball can move the match)
            predicts how far it does: in the tensest tenth of balls it expected{" "}
            {tense.leverage.toFixed(1)}× a typical swing and {tense.realised.value.toFixed(1)}×
            happened. It is the pressure meter in every replay.
          </li>
          <li>
            <Strong>Momentum is a story, not a force.</Strong> Across{" "}
            {MOMENTUM.states.toLocaleString("en-IN")} moments, a surge adds a fraction of a run and
            no extra chance of winning. The replay shows it as what just happened.
          </li>
          <li>
            <Strong>Clutch is not a skill you can measure.</Strong> A batter&apos;s record under
            pressure in odd seasons predicts even seasons with r ={" "}
            {clutch === null ? "—" : clutch.toFixed(2)}, too low for a rating, so there is none.
          </li>
          <li>
            <Strong>Rivalries do not repeat.</Strong> Past head-to-heads add nothing to form, and
            even form is weak: the side in better form wins 53% of meetings.
          </li>
        </ul>
      </Section>

      <Section id="teams" title="Rebuilding 19 league tables to the decimal">
        <p>
          Net run rate has rules most fans never see: a side bowled out is charged its full overs, a
          rain-shortened chase credits the side batting first with the target minus one, and an
          umpire&apos;s seven-ball over still counts as one over. With those rules, 12 fixtures
          abandoned before a ball and one voided match, every league table since 2008 is rebuilt
          from the balls and matches the official one, points and net run rate included.
        </p>
      </Section>

      <Section id="simulator" title="A simulator that admits a coin flip">
        <p>
          The Match Simulator plays any two sides from any season ball by ball with the ball-outcome
          model: extras and run outs at league rates, each over&apos;s bowler drawn from how
          captains used them (four overs each, never twice running, and only if the innings can
          still be finished), and a draw of pitch and conditions shared by both innings. All 10,000
          simulations step forward together as numpy arrays, about {sim.timing.seconds.toFixed(1)}{" "}
          seconds on a laptop.
        </p>
        <p>
          Backtested on every match of {seasonSpan(sim.test)} before a ball was bowled, its
          first-innings totals are calibrated ({pct(sim.first_innings.coverage_80, 0)} inside the
          simulated 80% range). Its pick of the winner scored a Brier of{" "}
          {sim.win.simulator.brier.toFixed(3)} against {sim.win.coin_flip.brier.toFixed(3)} for a
          coin flip: no better. That is the honest answer for T20 between professional sides, and
          the page says it in plain words next to every result.
        </p>
        <p>
          Simulated chases also ran about ten points pessimistic, so the replay&apos;s what-if does
          not trust them alone: it starts from the calibrated win probability at the real score and
          adds only the simulated change from your edit.
        </p>
      </Section>

      <Section id="engineering" title="Engineering for zero rupees">
        <p>
          CricIQ is a modular monolith: one data pipeline, one ML package, one API and one web app.
          The serving data is a read-only DuckDB file baked into the API image, with no database
          server to run or pay for. Model versions are committed with their evaluations and gated on
          test scores; deploys only score, never retrain. Everything about the real matches is
          computed at build time, so a match page is one payload and the replay runs entirely in the
          browser.
        </p>
        <p>
          The web app runs on Vercel and the API on Render&apos;s free tier, which sleeps when idle.
          That cost a real bug: what-ifs failed while the API woke. The fix was to start waking it
          the moment a replay or the simulator opens, and to retry with an honest &quot;waking
          up&quot; message instead of an error.
        </p>
        <p>
          Quality is enforced, not hoped for: strict typing, Python and frontend unit tests,
          end-to-end tests on desktop and mobile against a real API, an accessibility scan of every
          key page, and a CI job that builds the API image from live Cricsheet data and validates it
          on every push.
        </p>
      </Section>

      <Section id="next" title="What I would do next">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <Strong>More cricket per player.</Strong> Cricsheet also covers the BBL, PSL, CPL, SA20
            and T20 internationals; pooling them would give every player far more evidence.
          </li>
          <li>
            <Strong>Players who change.</Strong> The ball model rates each player once; a strength
            that drifts season to season would capture peaks and declines.
          </li>
          <li>
            <Strong>How chases are played.</Strong> Modelling intent under a rising required rate,
            and Impact Player substitutions, would fix the simulator&apos;s pessimistic chases.
          </li>
          <li>
            <Strong>Conditions.</Strong> Pitch and dew are not in the data. A licensed source would
            be the most valuable addition to pre-match predictions.
          </li>
        </ul>
        <p>
          Every number above is live on the site: <A href="/ipl/models">Model Insights</A> shows
          each model against its baseline, the <A href="/ipl/lab">Analytics Lab</A> has the full
          tests, and <A href="/about">About &amp; Methodology</A> explains every metric in plain
          terms. Or just <A href="/ipl/matches/1181768">replay the 2019 final</A>.
        </p>
      </Section>
    </article>
  );
}
