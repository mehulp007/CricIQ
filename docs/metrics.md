# CricIQ Metrics

Definitions of the numbers CricIQ derives itself, with their formulas, why they are built this
way, and where they fall short. Model outputs (win probability, score projection, ball outcome)
are documented in the [model cards](model-cards/). Every figure quoted here comes from the
current data; the generated [ratings model card](model-cards/ratings.md) has the full tables.

## Par

**What an average IPL player would have produced from the same balls.**

For each season `s` and phase `p` (powerplay, middle, death; see `config/phases.yaml`), the league
rate of an outcome `x` per ball is

```
rate(x, s, p) = sum of x over every ball in (s, p) / balls in (s, p)
```

and a player's par is that rate summed over their own balls:

```
par(x) = sum over the player's balls b of rate(x, season(b), phase(b))
```

Batting uses balls faced (wides excluded) for runs, dismissals, boundaries and dot balls; bowling
uses legal balls for runs conceded (bat runs + wides + no-balls), wickets credited to the bowler,
boundaries and dot balls. Super overs are excluded.

- **Why:** a strike rate of 135 meant more in 2010 than in 2025, and more in the powerplay than at
  the death. Par removes both effects without a model, and summed over every player it reproduces
  the league exactly (a tested invariant).
- **Limits:** par knows the season and phase, not the venue, the match situation or the quality
  of the opposition. At the death it includes tail-enders, which flatters top-order batters a
  little.

Derived figures: **runs above par** (runs − par runs), **runs saved** (par runs − runs
conceded), and strike rate, economy, dot and boundary percentages against par.

## Win probability added (WPA)

Every ball's change in the batting side's win probability, from the
[win probability model](model-cards/win-probability.md), is credited to the batter on strike and,
negated, to the bowler:

```
WPA(batter) += WP_after(ball) − WP_before(ball)
WPA(bowler) −= WP_after(ball) − WP_before(ball)
```

Changes between innings belong to nobody. Summed over a career, WPA is roughly wins added. It
depends heavily on match situations a player does not choose, so it describes impact rather than
skill.

## CricIQ Ratings

A rating places a player among the regulars of the same seasons on one thing they do, from 0 to
100, after allowing for how much their record can be trusted. Ratings are a profile: there is no
overall rating and no "better player" verdict.

### Components

Every component is a sum of per-innings evidence `e` over an exposure `n`, oriented so higher is
better. Definitions live in `core/src/criciq_core/ratings.py`, shared by the fit and the API.

| Role | Component | Evidence per innings `e` | Exposure `n` | Shown as |
|---|---|---|---|---|
| Batting | Run scoring | runs − par runs | balls faced | runs per 100 balls above par |
| Batting | Survival | par dismissals − dismissals | balls faced | dismissals avoided per 100 balls |
| Batting | Powerplay, Middle overs, Death overs | runs − par runs in that phase | balls in the phase | runs per 100 balls above par |
| Batting | Chasing | runs − par runs in the second innings | balls faced chasing | runs per 100 balls above par |
| Batting | Impact | WPA while batting | innings | points per innings |
| Batting | Consistency | 1 if runs ≥ par runs, else 0 | innings with a ball faced | % of innings |
| Bowling | Economy | par runs − runs conceded | legal balls | runs saved per over |
| Bowling | Wicket-taking | wickets − par wickets | legal balls | wickets per 4 overs above par |
| Bowling | Powerplay, Middle overs, Death overs | par runs − runs in that phase | legal balls in the phase | runs saved per over |
| Bowling | Defending | par runs − runs in the second innings | legal balls | runs saved per over |
| Bowling | Impact | WPA while bowling | innings | points per innings |
| Bowling | Consistency | 1 if runs ≤ par runs, else 0 | innings with a ball bowled | % of innings |

### Formula

For a season window (any span of seasons a user picks):

```
record          v  = scale × Σe / Σn
qualified mean  μ  = Σe / Σn over the qualified players in the window
estimate        v̂  = scale × (Σe + k·μ) / (Σn + k)
uncertainty     se = scale × √(σ² / (Σn + k))
rating             = 100 × share of other qualified players with a lower estimate (ties count half)
90% interval       = ratings of v̂ − 1.645·se and v̂ + 1.645·se
```

- **Qualified players** define the reference: at least 300 balls in the role in the window, plus
  120 balls for a phase or chasing component and 10 innings for an innings component.
- **`k`** is the number of balls (or innings) of the qualified average blended into every
  record, fitted per component. The record's weight in the estimate is `n / (n + k)`.
- **`σ²`** is the noise per ball (or innings), pooled from how much a player's innings vary
  within a season: for innings `j` of a player-season with rate `v` and exposure `N`,
  `E[(e_j − v·n_j)²] = σ²·n_j·(1 − n_j/N)`. Innings are the units, so streaks within an innings
  count as noise rather than signal.
- Players are rated from 60 balls in the role; below the qualifying mark the interval is wide
  and the page says so.

### Fitting `k`

`k` is tuned so a player's shrunk record in one season best predicts the same player's next
season (squared error against each season's qualified average, weighted by the balls behind the
season being predicted). This is empirical Bayes: if talent were constant, the best `k` would be
the noise-to-signal ratio `σ²/τ²`, and a synthetic test checks that the tuning recovers it.

### Validation and stability

Fitted by `criciq-ml train ratings`, evaluated like the models, and committed under
`models/ratings/`:

- **Next season:** `k` is re-tuned on season pairs before 2023, and each season from 2023 on is
  predicted from the one before by par, the raw record and the shrunk record. The shrunk record
  beats the raw record for every component (the promotion gate) and par for most.
- **Year-to-year stability:** the correlation between a player's ratings in consecutive seasons.
  At least 0.3 is *high*, 0.15 *moderate*, below that *low*; low-stability ratings carry a
  warning in the app.
- **Odd/even seasons:** the correlation between a player's records in odd and in even seasons,
  for how reliable a career-length record is.

What it shows: economy against par and batting survival persist; wicket-taking against par is
mostly luck (it needs thousands of balls before the record outweighs the average), as are
powerplay batting and second-innings bowling within a single season. Current numbers are on
[Model Insights](https://criciq-eight.vercel.app/models) and in the
[ratings model card](model-cards/ratings.md).

### Limits

- Ratings rank players against the regulars of the same seasons; a 50 in a strong era is not the
  same player as a 50 in a weak one.
- The interval assumes the same noise per ball for everyone; for Impact, whose size depends on
  the match situation, it is approximate.
- Ratings describe what happened, adjusted for sample size; they do not forecast form, fitness or
  role changes.

## Similar players

**Style profile.** For a window, each player's profile is a handful of per-ball rates against par
and usage shares (`core/src/criciq_core/style.py`):

- Batting: strike rate, boundary rate, dot-ball rate and dismissal rate against par; sixes as a
  share of boundaries; share of balls faced in the powerplay and at the death; average batting
  position.
- Bowling: runs saved per over, dot-ball and boundary rates against par; share of overs in the
  powerplay and at the death; spin (1) or pace (0); balls per innings; wides and no-balls per 100
  balls.

Each feature is z-scored within the qualified players of the window (300+ balls), and two players
are similar when their profiles point the same way:

```
similarity(a, b) = cos(z_a, z_b) = z_a · z_b / (|z_a| |z_b|)
```

Candidates need 300 balls in the window and a player needs 120 for a profile of their own. A
feature at least 0.75 standard deviations from average is a **trait** ("Finisher", "Economical");
two players share a trait when both are past that mark in the same direction.

**Validation (retrieval):** from a player's profile in one season, how often is the closest of
next season's profiles the same player? Bowlers: about one time in five, and in the top five more
than half the time, against 2% and 12% by chance. Wicket rate against par was left out of the
bowling profile because it barely persists and only added noise.

**Limits:** a profile describes how a player has been used as much as how they play; a batter
moved up the order will drift towards openers.
