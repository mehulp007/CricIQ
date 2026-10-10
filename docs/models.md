# Models and results (IPL edition)

Everything CricIQ v1.0.0 measures on the IPL and how well each model does. Every model is
tested once on the 2025–2026 seasons it never saw, against a simple baseline. Model cards
with the full detail are in [model-cards/](model-cards/); formulas are in
[metrics.md](metrics.md). The results for every competition are in
[the v2 edition](https://github.com/mehulp007/CricIQ/blob/v2/docs/models.md).

## At a glance

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
| Quality | 280+ Python tests, 100+ frontend unit tests, 110+ end-to-end tests on desktop and mobile, axe WCAG 2.1 AA scan of every key page |
| Performance | Lighthouse 95–100 performance (mobile, throttled) and 100 on desktop; 100 accessibility and best practices on every key page |

## The data

Every IPL match since 2008 is ingested ball by ball from Cricsheet, normalized into a DuckDB warehouse
and validated before anything downstream sees it.

| | |
|---|---|
| Seasons | 2008–2026 (19) |
| Matches | 1,243 |
| Deliveries | 295,732 |
| Players | 816, with attributes for ~98% of those with a meaningful sample |
| Validation | 17 invariant checks + 6 golden scorecards, all passing ([report](data-quality-report.md)) |

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
that they never saw ([model card](model-cards/win-probability.md)):

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
and conformally calibrated ([model card](model-cards/score-projection.md)). Tested once on the
143 first innings of 2025–2026:

| Test seasons 2025–2026 | 80% range covers | Median error (runs) | Pinball |
|---|---|---|---|
| **CricIQ projection** | **80.3%** | **16.9** | **4.87** |
| Par for the era + historical spread | 79.7% | 18.4 | 5.46 |
| TV-style run-rate projection | — | 27.9 | — |

The median error beats par in 11 of 11 backtest seasons. Season bias stays within a few
runs either way, with no drift as totals rose by 30 runs across eras.

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
[model card](model-cards/ball-outcome.md)) predicts dot, 1, 2, 3, 4, 6 or wicket for every ball, and
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
