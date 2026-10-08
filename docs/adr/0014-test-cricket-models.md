# ADR-0014: Test cricket has models of its own design

- **Status:** Accepted
- **Date:** 2026-10-08

## Context

V2-6 adds men's Tests (895 matches from December 2001, about 1.7 million balls). Under ADR-0013
they form a model group of their own (`test`), trained on Tests only. But a Test is not a long
limited-overs match:

- It has up to four innings, declarations and follow-ons, and a third result, the **draw**, which
  comes from running out of time. A win probability must give three chances, not one.
- There is no over limit, so the limited-overs features (balls remaining, the chase equation, the
  death-overs dynamic programme, the required rate against par) do not exist.
- **Cricsheet records no sessions or times of day.** The time left in a match can only be
  estimated from the overs bowled.
- About 40 Tests are played a year. A single pair of validation years holds about 80 matches,
  and every ball of a Test shares one result.

The limited-overs win probability models are boosted trees. Fitted on Test states, the trees
scored a log loss of 0.836 on the 2012-2024 rolling origin, against 0.736 for a regression on the
same features: the context known before a match (the sides' ratings, the scoring era) is the same
for every ball of it, so trees split on it and memorise individual Tests.

## Decision

- **Win probability: a multinomial regression per innings**, over the batting side's three
  outcomes (lost, drawn, won), in `criciq_core.test_win_probability` so the models package fits
  it and the API runs it with plain numpy. Its match state is the lead (in the fourth innings, the
  runs needed and the rate they need), wickets in hand, the overs left and the scoring era (runs
  per wicket over the previous 40 Tests). That alone is the **baseline**.
- **Context known before the match**, from earlier Tests only (`criciq_ml.test_match.states`):
  each side's Elo-style rating from its results, home advantage, the XIs' Test records and the
  batting still to come. Each group enters as itself and scaled by the share of the match left,
  and joins an innings' model only if it lowers the pooled log loss of a rolling origin over the
  pre-test years (2012-2024), each year predicted from every earlier one. The test years
  (2025-2026) are touched once.
- **Time is estimated** as five days of 90 overs less the overs bowled (`SCHEDULED_OVERS`). It
  ignores rain, bad light and the breaks between innings (drawn Tests averaged 361 overs, not
  450); the model learns from history how much of the nominal time is really left. Replay days
  are estimated the same way, sharing a match's balls evenly between the dates it was played on.
- **Every innings is projected** (`criciq_ml.test_match.projection`): LightGBM quantile models of
  the runs still to come, for any innings (an innings ends by being bowled out, declaring,
  reaching a target or running out of time), conformally calibrated on held-out years, against
  par by innings and wickets down.
- **The ball-outcome model and the ratings are the shared ones**, with Test phases (the new ball,
  overs 1-20; the middle overs; the second new ball, 81 on) over four innings and no chase
  pressure. Test ratings judge wicket-taking per 20 overs and rate the fourth innings where
  limited-overs cricket rates the chase. Win probability added becomes expected result added: a
  win counts 1 and a draw a half.
- **No match simulator.** A five-day match turns on declarations and time, which a ball-by-ball
  simulation cannot know. The fourth-innings **chase what-if** (`/matches/{id}/chase`) and the
  **chase calculator** (`/chase`) run the win probability model on an edited or invented chase
  instead; the scoring step publishes the model's terms, the fourth-innings states and each
  side's rating after the last Test.
- **Test-only columns stay in Test databases.** The Test copy of the warehouse keeps the innings
  win, the days, declarations, follow-ons, forfeits and penalty runs; the Test serving database
  adds each side's innings to the match summaries and draws to the team tables. Limited-overs
  databases keep exactly their columns, so the IPL's serving data is unchanged.

## Consequences

- The Test win probability is easy to read and to run anywhere, but cannot find interactions it
  is not given; it is judged against the match state alone, and its card says how it did.
- The time left is the weakest input: a washed-out day is invisible until the overs stop.
- A Test replay is about 2,000 balls; the site plays it faster (up to 64x), jumps by day,
  innings and ten overs, and bundles only six featured Tests.
