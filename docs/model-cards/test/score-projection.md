# Model card: Test innings projection (1.0.0)

Where the innings being played will finish, as a range: the 5th to 95th percentiles of its final total. Every innings of a Test is projected. Trained on Tests only.

## What it is

- One LightGBM quantile model per level predicts the runs still to come, from the score, wickets in hand, the innings so far and the last ten overs, the lead, the overs left in the match (estimated: five days of 90 overs less the overs bowled), the innings number, the scoring era, the batting still to come and the fielding side's bowling strength.
- An innings ends when the side is bowled out, declares, reaches a fourth-innings target or runs out of time; the model learns all of these from history.
- Conformal shifts per level, measured on held-out years (2023-2024 for the test), make about the stated share of totals fall below each level.

## Results on the test years

Fitted on Tests before 2023, calibrated on 2023-2024, scored once on 2025-2026 (221 innings).

| | Pinball loss (runs) | Mean abs. error of the median | 80% range covers | Range width |
|---|---|---|---|---|
| Model | 17.56 | 62.6 runs | 76.6% | 188 runs |
| Par (by innings and wickets) | 18.70 | 67.4 runs | 78.4% | 208 runs |

| Innings | Model MAE | Par MAE | 80% range covers |
|---|---|---|---|
| First innings | 72.5 | 78.2 | 73.5% |
| Second innings | 68.4 | 69.7 | 81.2% |
| Third innings | 54.9 | 54.7 | 78.0% |
| Fourth innings | 39.9 | 59.9 | 70.1% |

## Backtest

Each year: fitted on the years before the previous two, calibrated on those two. Better than par in 13 of 13 years.

| Year | Pinball (model) | Pinball (par) | 80% range covers |
|---|---|---|---|
| 2014 | 18.10 | 19.04 | 83.5% |
| 2015 | 17.20 | 18.17 | 86.2% |
| 2016 | 18.87 | 19.73 | 73.3% |
| 2017 | 16.79 | 17.90 | 80.8% |
| 2018 | 16.52 | 16.71 | 80.7% |
| 2019 | 18.63 | 19.87 | 78.0% |
| 2020 | 16.56 | 17.76 | 81.5% |
| 2021 | 16.25 | 17.79 | 83.4% |
| 2022 | 16.22 | 17.86 | 79.2% |
| 2023 | 16.53 | 17.82 | 75.8% |
| 2024 | 16.44 | 17.56 | 80.9% |
| 2025 | 17.54 | 18.89 | 74.6% |
| 2026 | 17.74 | 18.32 | 81.2% |

## Limits

- Declarations depend on the captain and the match situation; the model only knows how such innings ended before.
- No pitch or weather data.
