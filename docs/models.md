# Models and results

Everything CricIQ measures and how well each model does, competition by competition. Every
model is tested once on the 2025–2026 matches it never saw, against a simple baseline. Model
cards with the full detail are in [model-cards/](model-cards/); formulas are in
[metrics.md](metrics.md).

## The IPL at a glance

The IPL's models, the first built; every competition's results are in its Model Insights page and
in the sections below.

| | Result (tested once on the 2025–2026 seasons, never used for training or tuning) |
|---|---|
| Win probability | Log loss 0.510 vs 0.549 for a logistic baseline (95% CI of the gain excludes zero); the side it favours goes on to win after 74.2% of balls (baseline 70.5%), and its chances are off by 3.9 points on average |
| Score projection | 80% range covers 80.3% of first-innings totals; median error 16.9 runs vs 18.4 for par |
| Ball outcome | 1.07% better log loss than phase-and-wickets frequencies; better in 11 of 11 backtest seasons |
| Matchups | Head-to-head prior fitted by empirical Bayes (355 balls); raw records predict a pair's future far worse than shrunk ones |
| Ratings | 16 rating components shrunk by empirical Bayes: the shrunk record predicts a player's next season better than the raw record for all 16; year-to-year stability reported per component |
| Pressure | Leverage of every ball from what-if win probabilities; expected and realised next-ball swings agree in every tenth, from 0.09× to 2.9× a typical ball |
| League tables | Rebuilt from the balls for all 19 seasons and identical to the official tables, net run rate included; the build fails if they ever differ |
| Simulator | 10,000 complete matches in half a second on a laptop; first-innings totals calibrated on 2025–2026 (PIT uniform); pre-match winners no better than a coin flip, reported as such |
| Quality | 480+ Python tests, 120+ frontend unit tests, 240 end-to-end tests on desktop and mobile, axe WCAG 2.1 AA scan of every key page |
| Performance | Lighthouse 92–95 performance (mobile, throttled) on every competition's key pages, served locally; 100 accessibility, best practices and SEO; API warm p95 under 200 ms |

## The data

Every match is ingested ball by ball from Cricsheet, normalized into one DuckDB warehouse and
validated before anything downstream sees it (in October 2026; the sync adds new matches):

| Competition | From | Matches | Balls |
|---|---|---|---|
| Men's Tests | 2001 | 895 | 1,722,675 |
| Men's ODIs | 2002 | 2,581 | 1,368,605 |
| Men's T20Is | 2005 | 3,572 | 805,397 |
| IPL | 2008 | 1,243 | 295,732 |
| Big Bash League | 2011/12 | 662 | 153,250 |
| Caribbean Premier League | 2013 | 443 | 103,230 |
| Pakistan Super League | 2016 | 357 | 83,799 |
| SA20 | 2023 | 130 | 29,020 |

Invariant checks and golden scorecards guard every build ([report](data-quality-report.md)),
all 19 IPL tables must match the official ones, and 27 known international results (every major
tournament's champion, complete Test series) must be reproduced. The IPL alone has 816 players,
with attributes for about 98% of those with a meaningful sample. What follows is the IPL's story
first, where CricIQ began:

What the exploration found, and how it shapes the models ([notebook](../notebooks/01_eda.ipynb)):

- **About 1,200 outcomes, not 300k rows.** Deliveries within a match share one result, so models stay
  modest and are split by season.
- **Scores rose about 27 runs in the Impact Player era** (163 → 190 average first-innings total), so
  every model gets an as-of run-environment feature and is tested on the latest seasons.
- **The median batter–bowler pair has faced just 5 balls**, so matchup estimates are shrunk toward
  sensible baselines instead of over-reading tiny samples.

Details: [data pipeline](data-pipeline.md) · [data dictionary](data-dictionary.md)

## The win probability model

Two monotonic LightGBM models (first innings and chase), tested once on the 144 matches of 2025–2026
that they never saw ([model card](model-cards/win-probability-ipl.md)):

| Test seasons 2025–2026 | Log loss | Brier | ECE | AUC |
|---|---|---|---|---|
| **CricIQ win probability** | **0.510** | **0.168** | 0.039 | 0.832 |
| Boosted trees on the match state only | 0.543 | 0.182 | 0.020 | 0.795 |
| Logistic regression on the match state | 0.549 | 0.184 | 0.034 | 0.791 |

- **Better than the baseline, with uncertainty measured honestly:** +0.039 log loss (95% CI +0.012 to
  +0.067), resampling whole matches because balls within a match are correlated. A season-by-season
  backtest (2016–2026) is published too: the model wins 7 of 11 seasons.
- **Leak-free by construction:** every feature uses only that ball or earlier matches. A test deletes
  and rewrites all later matches and checks that no earlier feature changes.
- **Honest negative results:** player, venue and squad strength were built as-of and tested season by
  season. None improved on the match state plus the scoring era, so none is used.
- **Sharp at the finish:** a WASP-style dynamic programme computes the exact chance of a chase from
  runs, balls and wickets, where data is thinnest.
- **Every choice made on validation data:** hyperparameters, calibration (none vs Platt, decided by a
  rolling origin) and features. Model versions are committed and gated; deploys only score
  ([ADR-0004](adr/0004-committed-models-precomputed-predictions.md)).

Experiments: [notebook 02](../notebooks/02_wp_experiments.ipynb) (LightGBM vs XGBoost vs CatBoost, the
chase feature, the 2019 final explained).

## The score projection model

Quantiles of the final first-innings total after every ball, predicted relative to the scoring era
and conformally calibrated ([model card](model-cards/score-projection-ipl.md)). Tested once on the
143 first innings of 2025–2026:

| Test seasons 2025–2026 | 80% range covers | Median error (runs) | Pinball |
|---|---|---|---|
| **CricIQ projection** | **80.3%** | **16.9** | **4.87** |
| Par for the era + historical spread | 79.7% | 18.4 | 5.46 |
| TV-style run-rate projection | — | 27.9 | — |

The median error beats par in 11 of 11 backtest seasons. Season bias stays within a few
runs either way, with no drift as totals rose by 30 runs across eras.

## Every kind of cricket, its own models (v2)

Every competition's models learn from its own kind of cricket only
([ADR-0013](adr/0013-models-per-group.md)): the **IPL** alone; the **BBL, CPL, PSL and SA20**
together, with no IPL and no internationals; **men's T20Is** alone; **ODIs** alone; and **Tests**
alone. A player's
record inside a model counts only that kind of cricket. Each group is trained with one command
on a laptop and judged once on its 2025–2026 matches ([how to train](training.md)):

| Test, 2025–2026 | Leagues (BBL, CPL, PSL, SA20) | Men's T20Is |
|---|---|---|
| Trained on | 1,563 league matches, 2011–2026 | 3,480 T20Is, 2005–2026 |
| Win probability, log loss | 0.504 vs 0.516 (baseline), 270 matches: ahead, 95% interval −0.001 to +0.024 | **0.432 vs 0.458**, 952 matches: better, 95% interval +0.017 to +0.034 |
| Score projection, median error | **16.8 runs** vs 18.2 for par; 80% range holds 79.6% | **18.1 runs** vs 22.2 for par; 80% range holds 81.7% |
| Ball outcome, log loss | **1.4726** vs 1.4919, better in 11 of 11 backtest years | **1.4430** vs 1.4588, better in 11 of 11 backtest years |
| Simulator | Served for **all four** (PIT chi-square 7.0, 14.9, 10.4 and 4.2 against 16.9) | **Served**: 152.0 simulated against 153.8 actual, 80.8% inside the 80% range, PIT chi-square 6.5 |

For the leagues' win probability, the features were chosen again on the pre-test years
(2016–2024) only: with players' records counting league games alone, the squads' and the
crease batters' records made the first innings worse, so version 1.1.0 leaves them out (log
loss 0.638 against 0.649 before the test years, and 0.504 against 0.512 on the test). The
T20Is' model keeps them: international players' records are long.

**The trade-off.** Until these models the leagues and T20Is shared one model trained on every T20
competition at once (V2-3, [ADR-0010](adr/0010-pooled-t20-models.md)). On the same test
matches its win probability scored 0.545, 0.477, 0.472, 0.511 and 0.432 on the BBL, CPL, PSL,
SA20 and T20Is; the groups' own models score 0.543, 0.496, 0.474, 0.507 and 0.432: better on the
BBL and SA20, level on T20Is and the PSL, and behind on the CPL, where players' IPL and
international records helped. The IPL kept its own models all along: the pooled versions were
not better on the IPL's test seasons.

**Why the T20I simulator first failed, and how it was fixed.** T20I scoring jumped in 2025–26
(matches between associate sides from about 138 runs to 148), more than the ball model's scoring
era moves it, so simulated totals ran 8 runs short (146.0 against 154.1; PIT chi-square 70.9). A
level calibrated once on 2023–24 did not carry over and was dropped. What works is following the
recent scoring level: before each match, the scoring era is moved so the ball model's expected
runs over the previous matches equal the runs actually scored, using only matches already
played; the window (240 T20Is) is chosen on the validation years. With the level followed, the
spread of match conditions is chosen to make the validation years' PIT most uniform (the gate's
own test), a choice made after a first backtest showed the test ranges too wide. The same pair
lets the PSL's simulator pass too. Model cards: [leagues](model-cards/leagues/),
[T20Is](model-cards/t20i/).

## Every competition on the site (v2)

On the `v2` branch the site covers the IPL, BBL, PSL, CPL, SA20, men's T20Is, ODIs and Tests. A switcher in the
top bar picks the competition, every data page lives under it (`/ipl/matches`, `/t20i/teams`,
`/bbl/players/...`), and the v1 URLs redirect to the IPL's. Each competition has its own serving
database, so its replays, teams, matchups and simulator read only its own matches
([ADR-0011](adr/0011-one-serving-database-per-competition.md)); the API is
`/api/v2/{competition}/...`. National sides get records by year and by opponent instead of league
tables, players get a tab for every competition they played in and for all T20, and the leagues'
tables are computed from results (the IPL's are checked against the official ones).

## ODIs: their own models (v2)

Men's ODIs (2,576 matches from 2002) are on the site with every page, and with models of their
own: a 50-over match paces itself differently, so ODIs are not pooled with T20
([ADR-0012](adr/0012-models-per-format.md)). Each model was built with the T20 protocol and
tested once on the 2025–2026 ODIs (174 matches):

| ODI test, 2025–2026 | CricIQ | Baseline |
|---|---|---|
| Win probability, log loss | 0.550 | 0.552 (logistic regression): level, the 95% interval includes no gain |
| Score projection, median error | 31.2 runs, 80% range holds 82.6% | 38.0 runs (par for the era) |
| Ball outcome, log loss | 1.2076, better in 11 of 11 backtest years | 1.2210 (phase and wickets) |
| Simulator, first-innings totals | PIT χ² 14.0 (threshold 16.9), 88.7% in the 80% range | — |

The projection, ball model, ratings and simulator pass clearly; the win probability model is only
level with a logistic regression on the match state, and the site says so. Model cards:
[win probability](model-cards/odi/win-probability.md),
[score projection](model-cards/odi/score-projection.md),
[ball outcome](model-cards/odi/ball-outcome.md), [ratings](model-cards/odi/ratings.md),
[simulator](model-cards/odi/simulator.md).

## Tests: models of their own design (v2)

Men's Tests (895 matches from December 2001) have every page, and models built for a match of
four innings that can be drawn ([ADR-0014](adr/0014-test-cricket-models.md)), trained on
Tests only and tested once on the 59 Tests of 2025–2026:

| Test, 2025–2026 | CricIQ | Baseline |
|---|---|---|
| Win probability (win, draw, loss), log loss | **0.633**, Brier 0.367; better in 12 of 15 backtest years | 0.651, Brier 0.384 (the match state alone): ahead, 95% interval −0.045 to +0.074 |
| Innings projection, mean miss | **63 runs**, 80% range holds 76.6%; better in 13 of 13 backtest years | 67 runs (par by innings and wickets) |
| Ball outcome, log loss | **0.9879**, better in 13 of 13 backtest years | 1.0005 (phase and wickets) |
| Ratings | 10 components highly stable, 4 moderately, 2 low | — |

- **Three outcomes.** A draw comes from running out of time, so every replay shows the chances
  of a win, a draw and a defeat after every ball. The model is a multinomial regression per
  innings on the lead (or the runs needed), wickets in hand, the overs left and the scoring era,
  plus what earlier Tests say about the two sides (an Elo-style rating) and home advantage,
  chosen on a rolling origin over 2012–2024. It is clearly better than the match state alone in
  the first innings (log loss 0.768 against 0.865), when the sides' strength matters most, and
  level later, when the state says most.
- **Why not boosted trees.** With one result shared by about 2,000 balls and only about 800
  Tests, trees split on the pre-match context and memorised individual matches: 0.836 on the
  rolling origin, against 0.736 for the regression.
- **Time is estimated.** Cricsheet records no sessions, so the overs left are five days of 90 overs
  less those bowled (drawn Tests averaged 361 overs, so the model learns how much is really
  left), and replay days are estimated by sharing a match's overs between its dates.
- **No simulator, a chase calculator instead.** A Test turns on declarations and time. The
  replay's fourth innings has a chase what-if (change the runs needed, wickets or overs left), and
  the Chase calculator sets up a chase between any two sides; both run the win probability model.

Model cards: [win probability](model-cards/test/win-probability.md),
[innings projection](model-cards/test/score-projection.md),
[ball outcome](model-cards/test/ball-outcome.md), [ratings](model-cards/test/ratings.md).

## Series, tournaments and careers across formats (v2)

International cricket is followed by series and tournaments, so Tests, ODIs and T20Is have them
([ADR-0015](adr/0015-series-and-tournaments.md)), built from each match's Cricsheet event:

- **Series and tournaments.** Matches of one event within a few weeks are one series (two sides:
  "Australia won 4–1") or tournament (more: tables, knockouts and champion). The World Cup's,
  T20 World Cup's and others' changing names are joined by `config/events.yaml`; unlabelled group
  stages are split into the sides that played each other. Every page has the matches, the top
  run-scorers and wicket-takers, and the players who moved the results most.
- **Checked against what happened.** Every World Cup, Champions Trophy, T20 World Cup and World
  Test Championship final champion in the data, and a set of complete Test series, must be
  reproduced on every build (27 results). Missing matches are said out loud: the 2005 Ashes is
  missing its third Test in Cricsheet, so its page shows four Tests and says one is not in the
  data, and tables note that Afghanistan's matches are absent.
- **Head to head in every format**, with the two sides' series record; a player's career in every
  competition (averages, hundreds, best figures) with their ratings side by side, each among their
  own format's players; and Compare across formats (a player's Tests beside another's ODIs, each
  against its own par).
- **Two Analytics Lab notes across formats.** The toss is worth a little in Tests (toss winners
  take 53.6% of the results) and in the four franchise leagues (54.7%, where most bowl first), and
  nothing measurable in ODIs, T20Is or the IPL. Home advantage, balanced for each pair of sides'
  strength, grows with the length of the match: 60.3% in Tests, 59.2% in ODIs, 54.4% in T20Is,
  and none in the IPL (48.9%).

## Player Lab: measured against par

A strike rate of 135 meant something different in 2010 than in 2025, and in the powerplay than at the
death. Every Player Lab number therefore comes with **par**: what an average IPL player would have
produced from the same balls, using the league rate for each ball's season and phase. Summed over all
players, par reproduces the league exactly (a tested invariant).

- **Runs above par / runs saved:** Kohli has scored 235 runs more than par from his 6,926 balls; Bumrah
  has conceded 948 fewer.
- **Win probability added** credits every ball's change in the win probability to the batter and,
  negated, to the bowler. Narine (bowling), de Villiers and Warner (batting) lead the career totals.

Splits are precomputed as innings rows and ball-level cells, so any season window is one small
aggregate. They are checked against an independent recount of the raw Cricsheet JSON and known
scorecards (Kohli's 973 runs in 2016, Gayle's 175*, Alzarri Joseph's 6/12).

## CricIQ Ratings: trusting a record only as far as it deserves

A rating places a player among the regulars of the same seasons (300+ balls) on one thing they do,
from 0 to 100. Before ranking, each record against par is blended with the average:
`(own evidence + k × average) ÷ (own balls + k)`, where `k` is fitted per component so a season's
shrunk record best predicts the player's next season, and tested on 2023-2026. Every rating carries
a 90% interval. There is deliberately no overall number.

- Shrinking beats trusting the raw record for all 16 components when predicting a player's next
  season, by 15-50%.
- A batter's strike rate against par counts for half the estimate after about 460 balls; a bowler's
  economy after about 320; **wickets against par need about 3,800**, because over a season they are
  mostly luck. Runs conceded say more about a bowler than wickets do.
- Year-to-year stability is reported for every component, and the low ones (powerplay batting,
  wicket-taking, defending) are flagged in the app.

**Similar players** compare style profiles (per-ball rates against par and how a player is used),
z-scored within the same seasons, by cosine similarity. From one season's profile, the same bowler
is among the five closest next season 58% of the time (chance: 12%). **Compare** puts any two
players side by side over the same seasons. Formulas are in [docs/metrics.md](metrics.md).

## Pressure, momentum and the Analytics Lab

Before every ball, CricIQ tries each possible outcome, scores the resulting state with the win
probability model and weights the swings by how often each outcome happens: the **leverage**, or how
many typical balls this one is worth (the Leverage Index from baseball analytics). Its percentile is
the **pressure index** in the replay. Grouped into tenths, the swings it expects match the swings
that happen, from the calmest balls to the tensest (about 33× a typical ball: 3 or 4 needed off the
last ball).

The [Analytics Lab](https://criciq-eight.vercel.app/lab) publishes the tests, including the "no"s:

- **Momentum** (win probability gained over the last 12 balls) is descriptive, not predictive: after
  a 15-point surge sides score half a run more than expected over the next two overs, lose slightly
  more wickets, and do not win any more often than the win probability says.
- **Pressure** changes behaviour at the end of close chases: batters score about 8 runs per 100 balls
  above expectation and get out more often.
- **Clutch** is not a reliable skill: a batter's record under pressure in odd seasons predicts it in
  even seasons with r = 0.17, far below the 0.3 set in advance for a rating, so there is none.

## Teams: official tables, rebuilt

Every league table since 2008 is rebuilt from the balls: points, wins, and net run rate under the
playing conditions (a side bowled out is charged its full overs, a rain-revised chase credits the
side batting first with the target minus one, an umpire's seven-ball over counts as one). With 12
fixtures abandoned before a ball (missing from Cricsheet) and one voided match added, **all 19
seasons match the official tables exactly**, and the build fails if they ever stop matching.

Franchise pages split results by batting order, toss, home ground and stage, measure batting and
bowling in each phase against par, and find each side's greatest comebacks and costliest defeats
from the win probability of every ball. Head-to-head records are set against what each side's
form going into the match predicted, and the [Lab note](https://criciq-eight.vercel.app/lab/rivalries)
shows why: across every IPL rivalry, past head-to-head records add nothing to form, close-finish
records do not carry over, and even form is a weak guide (the side in better form wins 53% of the
time; a season's win rate predicts the next season's with r = 0.06).

## Match simulator and what-if, backtested

The [simulator](https://criciq-eight.vercel.app/simulator) plays any two sides from any season,
each XI picked from everyone who played for that franchise that year, ball by ball with the
ball-outcome model, in that season's scoring era: extras and run outs at league rates, each over's bowler drawn from how that
bowler was used (four overs each, never twice in a row, and only if the innings can still be
finished), and match conditions drawn per match and shared by both innings. Each player's
scorecard line is their typical (median) innings, so it reads in whole runs and wickets. All 10,000
simulations step forward together as numpy arrays, so 10,000 matches take about half a second on a laptop
([ADR-0006](adr/0006-simulator-in-the-api-with-numpy.md)).

Backtested on every 2025–2026 match before a ball was bowled, with a ball model that never saw
those seasons ([model card](model-cards/simulator.md)):

| Check | Result |
|---|---|
| First-innings totals | PIT uniform (χ² 10.7, 5% threshold 16.9); 86% inside the simulated 80% range |
| From the first ball of a chase | Brier 0.191 against 0.246 for the base chase rate, but chances run about 10 points low |
| Winner, pre-match | Brier 0.255 against 0.250 for a coin flip: no better, and the page says so |

Because simulated chases run low, the replay's **what-if** starts from the calibrated win
probability at the real score and adds only the simulated change from your edit.

## Matchup Lab: small samples, honestly

The longest IPL rivalry is about 160 balls; the median batter-bowler pair has met for 5. A ball-outcome
model (multinomial logistic regression with penalised batter and bowler effects,
[model card](model-cards/ball-outcome-ipl.md)) predicts dot, 1, 2, 3, 4, 6 or wicket for every ball, and
each head-to-head record is shrunk towards what it expects for those same balls. The prior's strength
is fitted across all 31,000 pairs (empirical Bayes): **355 balls**, so history never carries
more than about 31% of an estimate.

| Test seasons 2025–2026 | Log loss |
|---|---|
| **CricIQ ball model** | **1.4895** |
| Match situation only (no players) | 1.4945 |
| Phase and wickets frequencies | 1.5057 |

On the 15,102 test balls between pairs who had met before, raw head-to-head rates
predicted those balls far worse than the model (1.667 vs 1.464);
the shrunk record matched or beat it (1.464). Head-to-head records are mostly
noise around what the players' overall records already say.
