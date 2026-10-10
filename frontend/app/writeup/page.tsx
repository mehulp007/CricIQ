import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import {
  ProjectionBacktestChart,
  ReliabilityChart,
  SeriesLegend,
} from "@/components/models/charts";
import { scrollRegion } from "@/lib/a11y";
import type { LimitedOversId } from "@/lib/competitions";
import { CLUTCH, HOME, MOMENTUM, PRESSURE, TOSS } from "@/lib/lab";
import {
  BALL_OUTCOME,
  RATINGS,
  SCORE_PROJECTION,
  SIMULATOR,
  WIN_PROBABILITY,
  favouriteAccuracy,
  modelsFor,
  pooledWinProbabilityOn,
  seasonSpan,
  testModels,
  type ModelSet,
} from "@/lib/models";

export const metadata: Metadata = {
  title: "Building CricIQ",
  description:
    "What 4.6 million balls of men's cricket can and can't tell you: how CricIQ's win probability, score projection, matchups, ratings and match simulator were built for the IPL, four T20 leagues, T20Is, ODIs and Tests, each from its own matches, and tested on seasons they never saw.",
};

/** The data behind the site when this was written (the daily sync adds to it). */
const DATA = [
  { label: "Men's Tests", from: "2001", matches: "895", balls: "1,722,675" },
  { label: "Men's ODIs", from: "2002", matches: "2,581", balls: "1,368,605" },
  { label: "Men's T20Is", from: "2005", matches: "3,572", balls: "805,397" },
  { label: "IPL", from: "2008", matches: "1,243", balls: "295,732" },
  { label: "Big Bash League", from: "2011/12", matches: "662", balls: "153,250" },
  { label: "Caribbean Premier League", from: "2013", matches: "443", balls: "103,230" },
  { label: "Pakistan Super League", from: "2016", matches: "357", balls: "83,799" },
  { label: "SA20", from: "2023", matches: "130", balls: "29,020" },
] as const;

/** The limited-overs model groups, each trained on its own competitions only. */
const GROUPS: { label: string; models: ModelSet }[] = [
  { label: "IPL", models: modelsFor("ipl") },
  { label: "BBL, CPL, PSL and SA20", models: modelsFor("bbl") },
  { label: "Men's T20Is", models: modelsFor("t20i") },
  { label: "Men's ODIs", models: modelsFor("odi") },
];

/** The T20 competitions the pooled model of V2-3 also served, own model against pooled. */
const POOLED: { id: LimitedOversId; label: string }[] = [
  { id: "ipl", label: "IPL" },
  { id: "bbl", label: "BBL" },
  { id: "cpl", label: "CPL" },
  { id: "psl", label: "PSL" },
  { id: "sa20", label: "SA20" },
  { id: "t20i", label: "T20Is" },
];

/** Every competition with a simulator backtest. */
const SIMULATED: { id: LimitedOversId; label: string }[] = [
  { id: "ipl", label: "IPL" },
  { id: "bbl", label: "BBL" },
  { id: "cpl", label: "CPL" },
  { id: "psl", label: "PSL" },
  { id: "sa20", label: "SA20" },
  { id: "t20i", label: "T20Is" },
  { id: "odi", label: "ODIs" },
];

const th = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";
const td = "px-3 py-2 font-mono text-xs tabular-nums";

function pct(value: number, digits = 1): string {
  return `${(100 * value).toFixed(digits)}%`;
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(3)}`;
}

/** What a match-level bootstrap interval of the gain over a baseline says. */
function verdict(low: number, high: number): string {
  if (low > 0) return "Better";
  if (high < 0) return "Worse";
  return "Not clearly better";
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

function Table({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      className="overflow-x-auto rounded-2xl border border-border bg-card/70"
      {...scrollRegion(label)}
    >
      <table className="w-full min-w-[34rem] text-sm">
        <caption className="sr-only">{label}</caption>
        {children}
      </table>
    </div>
  );
}

export default function WriteupPage() {
  const wp = WIN_PROBABILITY.test;
  const sp = SCORE_PROJECTION.test;
  const sim = SIMULATOR;
  const tested = seasonSpan(WIN_PROBABILITY.splits.test);
  const accuracy = favouriteAccuracy(wp.reliability);
  const history = BALL_OUTCOME.matchups.all;
  const tense = PRESSURE.swing_check[PRESSURE.swing_check.length - 1];
  const clutch = CLUTCH.roles.batting.split_half_r;
  const death = sp.by_phase.find((r) => r.phase === "death");
  const powerplay = sp.by_phase.find((r) => r.phase === "powerplay");
  const wpSeasons = WIN_PROBABILITY.backtest.filter(
    (r) => r.model_log_loss < r.baseline_log_loss,
  ).length;

  const tossTests = TOSS.formats.find((f) => f.key === "test");
  const tossLeagues = TOSS.formats.find((f) => f.key === "leagues");
  const homeOf = (key: string) => HOME.formats.find((f) => f.key === key)?.balanced?.share.value;

  const tests = testModels();
  const twp = tests.winProbability;
  const tsp = tests.scoreProjection;
  const testYears = seasonSpan(twp.splits.test);
  const testSeasons = twp.backtest.filter((r) => r.model_log_loss < r.baseline_log_loss).length;
  const trees = twp.alternatives.find((a) => a.model !== "multinomial regression (served)");
  const served = twp.alternatives.find((a) => a.model === "multinomial regression (served)");
  const fourth = tsp.test.by_innings.find((r) => r.innings_no === 4);

  const ballGains = [...GROUPS.map((g) => g.models.ballOutcome), tests.ballOutcome].map(
    (b) => 1 - b.test.model.log_loss / b.test.baseline.log_loss,
  );
  const t20i = modelsFor("t20i");
  const odi = modelsFor("odi");
  const leagues = modelsFor("bbl");

  return (
    <article className="flex max-w-3xl flex-col gap-12">
      <header className="flex flex-col gap-4">
        <p className="text-xs tracking-wide text-muted-foreground uppercase">
          The write-up · October 2026 · about 20 minutes
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Building CricIQ</h1>
        <p className="text-lg leading-8 text-muted-foreground">
          What 4.6 million balls of men&apos;s cricket can and can&apos;t tell you, and how to build
          a cricket analytics product that says which is which: from one T20 league to Tests, each
          kind of cricket modelled from its own matches.
        </p>
        <p className="text-sm text-muted-foreground">By Mehul Patil</p>
      </header>

      <Section id="short" title="The short version">
        <p>
          CricIQ began with every IPL delivery since 2008 and now covers men&apos;s Tests, ODIs and
          T20 internationals and four more T20 leagues (the BBL, CPL, PSL and SA20). For each of
          them you can replay any match ball by ball with each side&apos;s chances, see a projected
          total with an honest range, read any batter against any bowler, rate players across
          formats and rebuild any season or international series, and for the limited-overs
          competitions play any two sides 10,000 times. New matches arrive within days of being
          played.
        </p>
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <Strong>Calibrated beats clever.</Strong> The IPL win probability is right about which
            side wins after {pct(accuracy)} of balls in {tested}, but the number that matters is
            that its 70% means 70%. Every competition&apos;s model is held to the same test.
          </li>
          <li>
            <Strong>Each kind of cricket learns from itself.</Strong> Five model groups (the IPL,
            the other four leagues, T20Is, ODIs and Tests) are each trained on their own matches
            only, even where pooling everything scored a little better.
          </li>
          <li>
            <Strong>A Test is not a long T20.</Strong> It has a third result, no over limit and no
            clock in the data, so it got models of its own design, and no simulator.
          </li>
          <li>
            <Strong>Most of cricket is noise.</Strong> In every format the best ball-by-ball model
            is only {pct(Math.min(...ballGains))} to {pct(Math.max(...ballGains))} sharper than the
            averages, and before a ball is bowled an IPL match is a coin flip.
          </li>
          <li>
            <Strong>Say no out loud.</Strong> Features, momentum, clutch and one whole simulator
            failed their tests. Each failure is on the site.
          </li>
        </ul>
      </Section>

      <Section id="data" title="9,883 matches, not 4.6 million rows">
        <p>
          The data is <A href="https://cricsheet.org">Cricsheet</A>&apos;s ball-by-ball record of
          eight competitions, men&apos;s cricket only. When this was written it held:
        </p>
        <Table label="Matches and balls in each competition">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={th}>
                Competition
              </th>
              <th scope="col" className={th}>
                From
              </th>
              <th scope="col" className={`${th} text-right`}>
                Matches
              </th>
              <th scope="col" className={`${th} text-right`}>
                Balls
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {DATA.map((d) => (
              <tr key={d.label}>
                <th scope="row" className="px-3 py-2 text-left text-sm font-normal text-foreground">
                  {d.label}
                </th>
                <td className={td}>{d.from}</td>
                <td className={`${td} text-right`}>{d.matches}</td>
                <td className={`${td} text-right`}>{d.balls}</td>
              </tr>
            ))}
          </tbody>
        </Table>
        <p>
          It looks like a big dataset. It is not. Every ball in a match shares one result, so for
          anything about winning the honest sample is the matches, and per model it is smaller
          still: the IPL has about 1,200, Tests under 900, and a single Test year about 40. That one
          fact shaped everything: models stay small, data is split by season and never by ball, and
          every uncertainty interval resamples whole matches.
        </p>
        <p>
          The second fact is drift. Average IPL first-innings totals rose by about 27 runs once the
          Impact Player rule arrived in 2023, and T20I scoring jumped again in 2025. A model that
          knows nothing about this under-projects every modern innings, so every model gets an as-of
          &quot;scoring era&quot; feature (runs per ball, or per wicket in Tests, over the previous
          matches of the same competition) and is always tested on the most recent seasons, the
          hardest ones.
        </p>
        <p>
          Before any of that, the data is checked: invariants such as legal balls per over, wickets,
          targets and rain-revised chases, golden scorecards and all 19 official IPL tables, which
          must match to the third decimal of net run rate or the build fails. Outside the IPL a
          scorer&apos;s slip or a new ground must not stop a refresh, so a match the checks cannot
          build is set aside with its reason and listed for review.
        </p>
      </Section>

      <Section id="groups" title="Each kind of cricket learns from its own matches">
        <p>
          The obvious way to add cricket is to pool it. I tried that first: one set of T20 models
          trained on every T20 competition at once, 6,391 matches instead of the IPL&apos;s 1,243.
          Judged by results it was reasonable. But what it learned from was mixed: a BBL
          replay&apos;s chances had learned from IPL and T20I matches, a T20I&apos;s from franchise
          leagues, and the pooled T20I simulator failed its test partly because league scoring rates
          leaked in.
        </p>
        <p>
          So the rule became simple:{" "}
          <Strong>every kind of cricket is modelled from its own matches</Strong>. There are five
          model groups, the IPL alone, the BBL, CPL, PSL and SA20 together, T20Is alone, ODIs alone
          and Tests alone, and nothing is borrowed across them, not even how far to trust a thin
          player record. Each group is one command that trains, tests, gates and publishes its
          models, and every model card says what it learned from.
        </p>
        <p>
          Purity has a price, and it is published. On the same test matches as the pooled model:
        </p>
        <Table label="Win probability log loss: each competition's own model against the pooled T20 model">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={th}>
                Competition
              </th>
              <th scope="col" className={`${th} text-right`}>
                Test matches
              </th>
              <th scope="col" className={`${th} text-right`}>
                Own model
              </th>
              <th scope="col" className={`${th} text-right`}>
                Pooled T20
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {POOLED.map(({ id, label }) => {
              const m = modelsFor(id);
              const own = m.results.winProbability ?? {
                matches: m.winProbability.test.matches,
                model: m.winProbability.test.model,
              };
              const pooled = pooledWinProbabilityOn(id.toUpperCase());
              return (
                <tr key={id}>
                  <th
                    scope="row"
                    className="px-3 py-2 text-left text-sm font-normal text-foreground"
                  >
                    {label}
                  </th>
                  <td className={`${td} text-right`}>{own.matches}</td>
                  <td className={`${td} text-right text-foreground`}>
                    {own.model.log_loss.toFixed(3)}
                  </td>
                  <td className={`${td} text-right`}>
                    {pooled ? pooled.model.log_loss.toFixed(3) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <p>
          Lower is better. The IPL, BBL and SA20 do better on their own, T20Is and the PSL are about
          level, and the CPL is behind. I kept the rule anyway: a number on a CPL page should come
          from franchise T20 like the CPL, and with 60 to 80 test matches per league the gaps are
          mostly within noise.
        </p>
      </Section>

      <Section id="win-probability" title="A win probability you can trust">
        <p>
          The heart of the replay is each side&apos;s chance of winning after every ball. For
          limited-overs cricket it is two gradient-boosted models (first innings and chase) with
          monotonic constraints, so more runs or more wickets in hand can never make a side less
          likely to win. On the IPL, tested once on the {wp.matches} matches of {tested}, it reaches
          a log loss of {wp.model.log_loss.toFixed(3)} against {wp.baseline.log_loss.toFixed(3)} for
          logistic regression on the match state, and beats that baseline in {wpSeasons} of{" "}
          {WIN_PROBABILITY.backtest.length} backtest seasons.
        </p>
        <Figure
          caption={`Does 70% mean 70%? Predicted chance against how often it happened, on every IPL ball of ${tested}. Points on the diagonal are perfectly calibrated.`}
        >
          <SeriesLegend />
          <ReliabilityChart model={wp.reliability} baseline={wp.baseline_reliability} />
        </Figure>
        <p>
          Every group gets the same model, the same baseline and the same single test on {tested}:
        </p>
        <Table label="Win probability on each group's test matches against the match-state baseline">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={th}>
                Group
              </th>
              <th scope="col" className={`${th} text-right`}>
                Matches
              </th>
              <th scope="col" className={`${th} text-right`}>
                CricIQ
              </th>
              <th scope="col" className={`${th} text-right`}>
                Baseline
              </th>
              <th scope="col" className={`${th} text-right`}>
                95% interval of the gain
              </th>
              <th scope="col" className={th}>
                Verdict
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {GROUPS.map(({ label, models }) => {
              const t = models.winProbability.test;
              return (
                <tr key={label}>
                  <th
                    scope="row"
                    className="px-3 py-2 text-left text-sm font-normal text-foreground"
                  >
                    {label}
                  </th>
                  <td className={`${td} text-right`}>{t.matches}</td>
                  <td className={`${td} text-right text-foreground`}>
                    {t.model.log_loss.toFixed(3)}
                  </td>
                  <td className={`${td} text-right`}>{t.baseline.log_loss.toFixed(3)}</td>
                  <td className={`${td} text-right`}>
                    {signed(t.vs_baseline.ci_low)} to {signed(t.vs_baseline.ci_high)}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {verdict(t.vs_baseline.ci_low, t.vs_baseline.ci_high)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <p>
          The ODI model is the honest exception: on {odi.winProbability.test.matches} test matches
          it is level with the baseline. It is calibrated and no worse, so it serves, and its card
          says plainly that it adds nothing measurable yet.
        </p>
        <p>
          The more interesting results are the ones that did not make it. I built as-of player
          quality, venue history and squad strength, all leak-free, and let forward selection on
          seasons before the test decide, group by group. For the IPL, the leagues and ODIs none
          improved on the match state plus the scoring era, so none is used. T20Is said yes: the
          strength of the two XIs, from their players&apos; records before the match, earned a
          place, because T20Is pit Test nations against associates in a way no league does. The same
          test gave a different answer on different cricket, which is the point of running it each
          time. A leakage test backs the &quot;leak-free&quot;: it rewrites every match after a
          given one and checks that no earlier feature moves.
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
          total relative to the scoring era, then shifts them with conformal calibration on held-out
          seasons. On the IPL&apos;s {tested} the 80% range held{" "}
          <Strong>{pct(sp.model.coverage80)}</Strong> of totals, and the median missed by{" "}
          {sp.model.mae.toFixed(1)} runs (par: {sp.par_baseline.mae.toFixed(1)}; the TV-style
          run-rate projection: {sp.run_rate.mae.toFixed(1)}).
          {death && powerplay
            ? ` The miss shrinks from ${Math.round(powerplay.model_mae)} runs in the powerplay to ${Math.round(death.model_mae)} at the death.`
            : ""}
        </p>
        <Figure caption="Median error of the IPL projection by season against par for the era: it stays ahead as scoring rose by 30 runs.">
          <SeriesLegend baseline="Par for the era" />
          <ProjectionBacktestChart rows={SCORE_PROJECTION.backtest} />
        </Figure>
        <p>
          The same holds in every group. The leagues&apos; median miss is{" "}
          {leagues.scoreProjection.test.model.mae.toFixed(1)} runs against{" "}
          {leagues.scoreProjection.test.par_baseline.mae.toFixed(1)} for par, T20Is&apos;{" "}
          {t20i.scoreProjection.test.model.mae.toFixed(1)} against{" "}
          {t20i.scoreProjection.test.par_baseline.mae.toFixed(1)}, and ODIs&apos;, over 50 overs,{" "}
          {odi.scoreProjection.test.model.mae.toFixed(1)} against{" "}
          {odi.scoreProjection.test.par_baseline.mae.toFixed(1)}, each with an 80% range that holds
          about 80% of totals.
        </p>
      </Section>

      <Section id="tests" title="A Test is not a long T20">
        <p>
          Tests broke almost every assumption in the code. There are up to four innings,
          declarations and follow-ons, and a third result, the <Strong>draw</Strong>, which comes
          from running out of time. With no over limit there are no balls remaining, no required
          rate and no death overs. And Cricsheet records no sessions or times of day, so the time
          left can only be estimated: five days of 90 overs, less the overs bowled. Drawn Tests
          actually averaged 361 overs, not 450, so the model learns from history how much of the
          nominal time is really there.
        </p>
        <p>
          The win probability gives three chances, win, draw and loss, with one multinomial
          regression per innings. Boosted trees, which serve every other format, lost clearly: on
          the rolling origin over 2012 to 2024 they scored a log loss of{" "}
          {trees ? trees.log_loss.toFixed(3) : "—"} against{" "}
          {served ? served.log_loss.toFixed(3) : "—"} for the regression. The context known before a
          Test (the sides&apos; ratings, the scoring era) is the same for every ball of it, so the
          trees split on it and memorised individual Tests.
        </p>
        <p>
          That context was offered to each innings&apos; model separately, and kept only where it
          helped earlier years: an Elo-style rating for each side from its Test results, home
          advantage, the XIs&apos; Test records and the batting still to come. Home advantage earned
          a place in every innings; the ratings only in the first. In the fourth innings, the chase,
          the state of the match says almost everything.
        </p>
        <PullQuote>
          On the {twp.test.matches} Tests of {testYears}, the model scored a log loss of{" "}
          {twp.test.model.log_loss.toFixed(3)} against {twp.test.baseline.log_loss.toFixed(3)} for
          the match state alone, and beat it in {testSeasons} of {twp.backtest.length} backtest
          years.
        </PullQuote>
        <p>
          With {twp.test.matches} test matches, the 95% interval of that gain runs from{" "}
          {signed(twp.test.vs_baseline.ci_low)} to {signed(twp.test.vs_baseline.ci_high)}: probably
          better, not proven, and the card says so. Every innings is also projected, with an 80%
          range that held {pct(tsp.test.model.coverage80)} of totals and a median miss of{" "}
          {tsp.test.model.mae.toFixed(1)} runs against {tsp.test.par_baseline.mae.toFixed(1)} for
          par{fourth ? `, ${fourth.model.mae.toFixed(1)} in the fourth innings` : ""}.
        </p>
        <p>
          There is deliberately <Strong>no Test simulator</Strong>. A five-day match turns on
          declarations, the weather and time, which a ball-by-ball simulation cannot know. Instead
          the <A href="/test/chase">chase calculator</A> and the replay&apos;s fourth-innings
          what-if run the win probability model on an invented or edited chase: how many runs, how
          many wickets, how many overs left.
        </p>
      </Section>

      <Section id="matchups" title="Five balls is not a rivalry">
        <p>
          The median batter-bowler pair in IPL history has met for five balls. Raw head-to-head
          records are mostly noise, so the Matchup Lab treats them the way a careful scout would. A
          ball-outcome model (a penalised multinomial regression over dot, 1, 2, 3, 4, 6 and wicket)
          says what each player&apos;s overall record expects, and each pair&apos;s history is
          blended with that expectation. How much to trust history is fitted across all pairs by
          empirical Bayes: in the IPL, history earns weight like{" "}
          {Math.round(BALL_OUTCOME.matchups.served_kappa)} balls of evidence would.
        </p>
        <PullQuote>
          On {history.balls.toLocaleString("en-IN")} IPL test balls between pairs who had met
          before, raw head-to-head rates scored a log loss of {history.raw.toFixed(3)}; the model
          alone, {history.model.toFixed(3)}.
        </PullQuote>
        <p>
          Every group has its own ball model with its own phases (the new ball, the middle overs and
          the second new ball in a Test), and the result is the same everywhere: about one percent
          sharper than the averages. The model powers next-ball odds and the simulator. It is served
          as a table of additive terms, so the API computes odds with plain arithmetic and no
          machine-learning library at runtime.
        </p>
      </Section>

      <Section id="ratings" title="Par, ratings, and how much to trust a record">
        <p>
          A strike rate of 135 meant something different in 2010 than in 2025, and in the powerplay
          than at the death. Every Player Lab number comes with <Strong>par</Strong>: what an
          average player of that competition would have produced from the same balls. Summed over
          all players, par reproduces the competition exactly, a tested invariant.
        </p>
        <p>
          CricIQ Ratings then rank players among the regulars of the same seasons on{" "}
          {RATINGS.components.length} separate skills, each record blended with the average by how
          much a sample of that size can be trusted. The fitted trust is revealing: in the IPL a
          batter&apos;s strike rate is half signal after about 460 balls, a bowler&apos;s economy
          after about 320, but <Strong>wickets need about 3,800</Strong>. Over a season, wickets are
          mostly luck; runs conceded say more about a bowler. There is deliberately no single
          overall number.
        </p>
        <p>
          Ratings are fitted per competition, so a player&apos;s BBL rating compares them with BBL
          players and their Test rating with Test players. Tests rate wicket-taking per 20 overs and
          the fourth innings where limited-overs cricket rates the chase, and win probability added
          becomes expected result added: a win counts one and a draw a half.
        </p>
      </Section>

      <Section id="lab" title="Testing ideas that could fail">
        <p>
          The Analytics Lab exists for ideas that sound true. Each got a test it could fail: four on
          the IPL&apos;s balls, two across every format.
        </p>
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
          <li>
            <Strong>The toss matters in Tests, and in the leagues.</Strong> The toss is random, so
            the toss winner&apos;s results measure it cleanly: they took{" "}
            {tossTests ? pct(tossTests.share.value) : "—"} of results in Tests and{" "}
            {tossLeagues ? pct(tossLeagues.share.value) : "—"} in the BBL, CPL, PSL and SA20, and
            nothing measurable in ODIs, T20Is or the IPL.
          </li>
          <li>
            <Strong>Home advantage grows with the match.</Strong> Balanced for each pair of
            sides&apos; strength, home sides took {pct(homeOf("test") ?? 0.5)} of results in Tests,{" "}
            {pct(homeOf("odi") ?? 0.5)} in ODIs and {pct(homeOf("t20i") ?? 0.5)} in T20Is, and none
            in the IPL ({pct(homeOf("ipl") ?? 0.5)}).
          </li>
        </ul>
      </Section>

      <Section id="teams" title="Rebuilding 19 league tables to the decimal">
        <p>
          Net run rate has rules most fans never see: a side bowled out is charged its full overs, a
          rain-shortened chase credits the side batting first with the target minus one, and an
          umpire&apos;s seven-ball over still counts as one over. With those rules, 12 fixtures
          abandoned before a ball and one voided match, every IPL table since 2008 is rebuilt from
          the balls and matches the official one, points and net run rate included. The same code
          builds every competition&apos;s season records; for Tests it counts draws, and a result
          reads &quot;won by an innings and 120 runs&quot; where it should.
        </p>
        <p>
          International cricket is followed by series and tournaments, which Cricsheet does not
          record: each match only names its event, inconsistently (the World Cup has had three
          names, and the 2005 Ashes is &quot;Australia tour of England and Scotland&quot;). Matches
          of one event within a few weeks become one series or tournament, with tables and
          knockouts, and every build must reproduce 27 known results: every World Cup, Champions
          Trophy, T20 World Cup and World Test Championship champion in the data, and a set of
          complete Test series. What the data lacks is said out loud: the 2005 Ashes is missing its
          third Test, and no table has Afghanistan&apos;s matches.
        </p>
      </Section>

      <Section id="simulator" title="A simulator that admits a coin flip">
        <p>
          The Match Simulator plays any two sides from any season ball by ball with the ball-outcome
          model: extras and run outs at the competition&apos;s rates, each over&apos;s bowler drawn
          from how captains used them (a full quota each, never twice running, and only if the
          innings can still be finished), and a draw of pitch and conditions shared by both innings.
          All 10,000 simulations step forward together as numpy arrays, about{" "}
          {sim.timing.seconds.toFixed(1)} seconds on a laptop for an IPL match.
        </p>
        <p>
          Each competition&apos;s simulator is backtested on every match of its test seasons before
          a ball was bowled, and served only if it passes: its first-innings totals must be
          calibrated, and the bowling rules must almost never have to give way.
        </p>
        <Table label="Simulator backtests: Brier score of its pick of the winner against a coin flip">
          <thead className="border-b border-border">
            <tr>
              <th scope="col" className={th}>
                Competition
              </th>
              <th scope="col" className={`${th} text-right`}>
                Totals inside the 80% range
              </th>
              <th scope="col" className={`${th} text-right`}>
                Simulator Brier
              </th>
              <th scope="col" className={`${th} text-right`}>
                Coin flip
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {SIMULATED.map(({ id, label }) => {
              const s = modelsFor(id).simulatorBacktest;
              if (!s) return null;
              return (
                <tr key={id}>
                  <th
                    scope="row"
                    className="px-3 py-2 text-left text-sm font-normal text-foreground"
                  >
                    {label}
                  </th>
                  <td className={`${td} text-right`}>{pct(s.first_innings.coverage_80, 0)}</td>
                  <td className={`${td} text-right text-foreground`}>
                    {s.win.simulator.brier.toFixed(3)}
                  </td>
                  <td className={`${td} text-right`}>{s.win.coin_flip.brier.toFixed(3)}</td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <p>
          In the IPL and the leagues its pick of the winner is within a whisker of a coin flip. That
          is the honest answer for T20 between professional sides, and the page says it in plain
          words next to every result. T20Is are different: when a Test nation meets an associate the
          result is far from a coin flip, and the simulator&apos;s Brier of{" "}
          {t20i.simulatorBacktest?.win.simulator.brier.toFixed(3) ?? "—"} shows it.
        </p>
        <p>
          The T20I simulator did not pass first time. The pooled version ran 7 runs short and made
          unequal sides look too even, because thin associate records were shrunk toward an average
          player; trained on T20Is alone it then ran 8 runs short of 2025–26, when T20I scoring
          jumped. Version 1.1.0 follows the recent scoring level and passes. Until then no T20I was
          simulated. Simulated IPL chases also ran about ten points pessimistic, so the
          replay&apos;s what-if does not trust them alone: it starts from the calibrated win
          probability at the real score and adds only the simulated change from your edit.
        </p>
      </Section>

      <Section id="sync" title="New matches within days">
        <p>
          Cricsheet publishes a match one to three days after it is played. A sync fetches the
          shortest recent feed that reaches back to the last one, compares every file with an ingest
          log of fingerprints to sort matches into new, corrected, unchanged or withdrawn, and
          applies only the changes. It then rebuilds the warehouse, validates it, rebuilds each
          competition&apos;s serving data and rescores every ball with the committed models, about
          two minutes end to end, and swaps the new data in only if all of that worked. Two
          incremental syncs on a deliberately stale copy produced data identical to a full rebuild,
          table by table.
        </p>
        <p>
          Syncing never retrains. Models are retrained deliberately, a group at a time, and a new
          version serves only if it passes its gate on the test seasons.
        </p>
      </Section>

      <Section id="engineering" title="Engineering on a budget">
        <p>
          CricIQ is a modular monolith: one data pipeline, one ML package, one API and one web app.
          One DuckDB warehouse holds every competition, with no database server to run or pay for;
          each competition is served from its own read-only DuckDB file, and each model group trains
          from its own copy of the warehouse. Model versions are committed with their evaluations
          and gated on test scores. Everything about the real matches is computed at build time, so
          a match page is one payload and the replay runs entirely in the browser, even a 2,000-ball
          Test, which plays at up to 64× and jumps by day, innings or ten overs.
        </p>
        <p>
          Training runs on a laptop and takes hours per group, so it is one command that can be left
          running: it trains, scores, rates and backtests, promotes only what passes, keeps going
          past a failure, resumes if interrupted and writes a summary to review afterwards.
        </p>
        <p>
          The first version ran on Vercel and Render&apos;s free tier, which sleeps when idle. That
          cost a real bug: what-ifs failed while the API woke. The fix was to start waking it the
          moment a replay or the simulator opens, and to retry with an honest &quot;waking up&quot;
          message instead of an error.
        </p>
        <p>
          All of cricket does not fit there: about 525 MB of serving data and an API that settles
          near 1 GB of memory, against the free instance&apos;s 512 MB. So the full version runs on
          your own machine instead: one command downloads Cricsheet, builds and validates every
          competition, scores every ball and serves a production build, and a scheduled sync keeps
          it current. Each database&apos;s memory is capped, every competition&apos;s cached pages
          answer within about a tenth of a second, and the hosted demo stays the IPL edition.
        </p>
        <p>
          Quality is enforced, not hoped for: strict typing, Python and frontend unit tests,
          end-to-end tests on desktop and mobile against a real API across the competitions, an
          accessibility scan of every key page, a regression test that keeps the IPL&apos;s serving
          data identical as the rest was added, and a CI job that builds the API image from live
          Cricsheet data and validates it on every push.
        </p>
      </Section>

      <Section id="next" title="What I would do next">
        <ul className="flex list-disc flex-col gap-2 pl-5">
          <li>
            <Strong>Players who change.</Strong> The ball model rates each player once; a strength
            that drifts season to season would capture peaks and declines.
          </li>
          <li>
            <Strong>How chases are played.</Strong> Modelling intent under a rising required rate,
            and Impact Player substitutions, would fix the simulator&apos;s pessimistic chases.
          </li>
          <li>
            <Strong>Conditions and time.</Strong> Pitch, dew and weather are not in the data, and
            Tests have no sessions or times of day. A licensed source would be the most valuable
            addition to pre-match predictions and to the time left in a Test.
          </li>
        </ul>
        <p>
          Every model number above is read from the same files as the site: Model Insights shows
          each group&apos;s models against their baselines (the <A href="/ipl/models">IPL</A>,{" "}
          <A href="/t20i/models">T20Is</A>, <A href="/odi/models">ODIs</A> and{" "}
          <A href="/test/models">Tests</A>), the <A href="/ipl/lab">Analytics Lab</A> has the full
          tests, and <A href="/about">About &amp; Methodology</A> explains every metric in plain
          terms. Or just <A href="/ipl/matches/1181768">replay the 2019 IPL final</A> or{" "}
          <A href="/test/matches/215010">Edgbaston 2005</A>.
        </p>
      </Section>
    </article>
  );
}
