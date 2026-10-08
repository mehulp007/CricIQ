# Model card: Test win probability (1.0.0)

For any moment of a men's Test: the chance that the side batting first wins, that the match is drawn, and that the other side wins. Trained on Tests only.

## What it is

- **Three outcomes.** A Test can be won, lost or drawn: a draw is what happens when time runs out. Every probability on the site is a triple that adds up to 100%.
- **A multinomial regression per innings** (four of them), on the match state: the lead (in the fourth innings, the runs needed and the rate they need), wickets in hand, the overs left and the scoring era (runs per wicket over the previous 40 Tests).
- **Context known before the match**, where it earned its place (below): each enters as itself and scaled by the share of the match still to play, since a stronger side has more time to show it.
- **Time left is estimated.** Cricsheet has no session or time-of-day data, so the overs left are five days of 90 overs less the overs bowled. That ignores rain, bad light and the breaks between innings: drawn Tests in the data averaged 361 overs, not 450. The model learns how much of the nominal time is really left from history, but it cannot know about a washed-out day.
- **A match's last ball carries its result**, not an estimate.

## Data

- 894 men's Tests from 2001 to 2026 (Cricsheet). Ties and awarded matches have no outcome to learn from.
- **Test:** fitted on every Test before 2025, scored once on 2025-2026 (59 Tests: 30 won by the side batting at the time of the last ball, 5 drawn). The test years were never used for any choice.
- **Choices** were made on a rolling origin over 2012-2024: each year predicted from a fit on every earlier year. About 40 Tests are played a year, so a single pair of validation years is too few to choose on.

## Context it uses

| Innings | Context added to the match state |
|---|---|
| First innings | Home advantage, The sides' ratings from earlier Tests |
| Second innings | The batting still to come, Home advantage, The XIs' Test records |
| Third innings | Home advantage |
| Fourth innings | Home advantage |

Each group was added while it lowered the rolling-origin log loss. The XIs' records and the batting still to come were tried in every innings.

## Results on the test years

| | Log loss | Brier | ECE (win / draw / loss) |
|---|---|---|---|
| Model | 0.6332 | 0.3674 | 0.063 / 0.039 / 0.028 |
| Baseline (match state only) | 0.6509 | 0.3835 | 0.029 / 0.022 / 0.026 |

Improvement over the baseline: **+0.0177** log loss (95% CI -0.0445 to +0.0743, resampling whole Tests): level with the baseline (the interval includes zero).

| Innings | Model log loss | Baseline |
|---|---|---|
| First innings | 0.7681 | 0.8648 |
| Second innings | 0.6343 | 0.6256 |
| Third innings | 0.5390 | 0.5140 |
| Fourth innings | 0.4830 | 0.4527 |

| Day (estimated) | Model log loss | Baseline |
|---|---|---|
| 1 | 0.7718 | 0.8438 |
| 2 | 0.5943 | 0.5902 |
| 3 | 0.5179 | 0.5014 |
| 4 | 0.6065 | 0.6095 |
| 5 | 0.5361 | 0.5137 |

## Backtest

Each year fitted on every earlier year. Better than the baseline in 12 of 15 years.

| Year | Tests | Model log loss | Baseline |
|---|---|---|---|
| 2012 | 42 | 0.7999 | 0.8505 |
| 2013 | 44 | 0.7324 | 0.8121 |
| 2014 | 41 | 0.8204 | 0.8090 |
| 2015 | 43 | 0.7049 | 0.7521 |
| 2016 | 47 | 0.7228 | 0.7804 |
| 2017 | 47 | 0.7263 | 0.8055 |
| 2018 | 47 | 0.6617 | 0.7270 |
| 2019 | 36 | 0.6203 | 0.6596 |
| 2020 | 22 | 0.7246 | 0.7277 |
| 2021 | 42 | 0.8020 | 0.8053 |
| 2022 | 43 | 0.8364 | 0.7863 |
| 2023 | 33 | 0.6794 | 0.7339 |
| 2024 | 50 | 0.6886 | 0.6479 |
| 2025 | 40 | 0.6587 | 0.6799 |
| 2026 | 19 | 0.5814 | 0.5887 |

## Why not boosted trees

The limited-overs models are boosted trees. For Tests they were fitted on the same features and rolling origin:

| Model | Rolling-origin log loss |
|---|---|
| Multinomial regression (served) | 0.7358 |
| Boosted trees | 0.8356 |

Every ball of a Test shares one result and there are only about 800 Tests, so trees split on the context that is the same for a whole match and memorise individual Tests. A regression cannot.

## Limits

- About 40 Tests a year: year-to-year results move a lot, and one surprising match weighs heavily.
- No pitch, weather or session data (out of scope): a turning pitch or a forecast of rain is invisible.
- Declarations are not modelled as decisions: the model only knows how such states turned out before.
- Not betting advice.
