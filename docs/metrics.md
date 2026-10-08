# CricIQ Metrics

Definitions of the numbers CricIQ derives itself, with their formulas, why they are built this
way, how they were validated, and where they fall short. Model outputs (win probability, score projection, ball outcome)
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

## Pressure (leverage)

**How much the next ball can move the match.** Shown in every replay as a pressure index and
explained in the Analytics Lab note
[What pressure does to batting](https://criciq-eight.vercel.app/lab/pressure). Code:
`ml/src/criciq_ml/leverage.py`.

For a match state `s`, each possible next ball `o` (a dot, 1, 2, 3, 4 or 6 runs, a wicket, or a
wide or no-ball) is applied to the state, every model feature is rebuilt, and the win probability
model scores the result:

```
swing(s)    = Σ_o p(o | s) · |WP(s after o) − WP(s)|
leverage(s) = swing(s) / mean swing over every historical state
pressure(s) = percentile of swing(s) among every historical state (0-100)
bands       : Low < 50 ≤ Medium < 80 ≤ High < 95 ≤ Very high
```

- `p(o | s)` is the league's rate of each outcome in that innings, phase and wickets-in-hand
  bucket (1-2, 3-4, 5-7, 8-10 in hand), with thin cells borrowing from the overall rates.
- Tree models move in steps, so every win probability in the swing is averaged over scores within
  four runs (triangular weights). This cut the ball-to-ball jitter of leverage by about 40%
  without blunting real spikes such as last-ball finishes; averaging over balls as well was tried
  and rejected because it flattened the end of chases.
- Once an innings is over there is no next ball, so leverage is empty.

**Why:** the Leverage Index from baseball analytics (Tango) has a natural scale (1 = a typical
ball) and comes straight from the win probability model, so situation, wickets and the chase
equation enter through a tested model rather than hand-picked weights. The percentile makes it
readable; in leverage terms, medium pressure starts at about 0.8×, high at 1.4× and very high at
2.4× a typical ball, and the tensest IPL balls (3 or 4 needed off the last ball) reach about 33×.

**Validation:** two tests.

- *The rebuilt states are right:* applying the ball that was actually bowled to a state
  reproduces every feature of the state that followed, exactly (a unit test over the fixture
  matches).
- *Leverage anticipates what happens:* grouping every ball since 2008 into tenths by leverage,
  the realised change in win probability on the next ball matches the expected one in every
  group, from 0.09× (expected) vs 0.09× (realised) for the calmest tenth to 2.88× vs 2.93× for
  the tensest.

**Limits:** leverage inherits the win probability model's view of each state; outcome rates are
the league's, not those of the batter and bowler at the crease; and "pressure" here is the match
situation, not what players feel.

## Momentum

**The change in the batting side's win probability over the last 12 legal balls**, in percentage
points, shown in every replay:

```
momentum(s) = 100 · (WP_batting(s) − WP_batting(last state with ≤ L − 12 legal balls))
```

where `L` is the legal balls bowled at `s`; in the first 12 balls of an innings it is measured
from the innings' first state.

**Why:** a hand-weighted "momentum index" of recent runs, wickets and dots would be arbitrary.
Measuring momentum on the scale the match is decided on makes it comparable across situations
and testable.

**Validation** (Analytics Lab: [Is momentum real?](https://criciq-eight.vercel.app/lab/momentum)):
from the end of every over with at least 12 balls on either side (about 41,000 moments in 1,242
matches), momentum was compared with the next 12 balls faced, measured against the ball-outcome
model's expectation (which knows the batter, bowler, phase, wickets, how settled the batter is and
the chase equation), and with the result. Intervals resample whole matches.

- Next 12 balls: +0.19 runs above expectation per 10 points of momentum (90%: +0.14 to +0.26).
  After a surge of 15+ points, +0.5 runs over the next two overs, against about 16 runs scored.
- Wickets: +0.013 per 10 points (90%: +0.007 to +0.020): sides on a run also lose slightly more
  wickets, so they are attacking, not suddenly better.
- Result: −0.42 points of win rate above win probability per 10 points of momentum (90%: −0.69 to
  −0.09). The win probability already prices momentum in, and if anything overreacts to a hot
  streak.

Momentum is therefore **descriptive, not predictive**; it is shown, but never used to adjust an
estimate.

**Limits:** twelve balls is one choice of window; the test uses the served models, which were
fitted on these seasons.

## Clutch (not a rating)

A rule set in advance allowed a clutch rating only if it proved reliable (split-half correlation above 0.3).
It did not.

```
clutch(player) = runs above expectation per 100 balls in balls at pressure ≥ 80
               − runs above expectation per 100 balls in all other balls
```

(for bowlers, runs saved), with "expectation" from the ball-outcome model as above, so a
player's overall ability is already accounted for.

**Validation** (Analytics Lab: [Is clutch a skill?](https://criciq-eight.vercel.app/lab/clutch)):
each career is split into odd and even seasons, and players with 60+ high-pressure balls in both
halves are compared. Batters: r = 0.17 across 104 players, against ±0.16 that shuffled halves
produce nine times in ten (permutation p ≈ 0.07): at most a faint signal. Bowlers: r = −0.06
across 110 (p ≈ 0.53): none. Even for the batters with 1,000+ high-pressure balls, career
clutch records carry 90% intervals about 20 runs per 100 balls wide.

Clutch is therefore reported as a research finding, not as a rating or a player label.

## League tables and net run rate

**Every season's league table, rebuilt from the scorecards.** Shown on the Teams pages. Code:
`pipelines/src/criciq_pipelines/teams.py`; reference: `config/league_tables.yaml`.

```
points       = 2 · won + no result     (a tie settled by a super over is a win)
order        : points, then wins, then net run rate
NRR          = 6 · Σ runs scored / Σ balls faced − 6 · Σ runs conceded / Σ balls bowled
```

Net run rate follows the playing conditions, over league matches with a result:

- a side bowled out is charged its full quota of overs, not the balls it lasted;
- when a chase is revised or ended by rain (D/L), the side batting first is credited with the
  target minus one from the overs the chasing side had;
- an over an umpire miscounted (five or seven legal balls) counts as one over.

Cricsheet has no record of league fixtures **abandoned without a ball bowled** (12 since 2008), but
each side took a point; they are listed in the config, as is one **voided** match (PBKS v DC at
Dharamsala, 8 May 2025, stopped for security reasons and replayed in full).

**Why:** a team page needs the season's standing as the IPL recorded it, and rebuilding it from
the balls (rather than copying it) makes every number on the page traceable to the same data.

**Validation:** the export compares the computed table with the official one (ESPNcricinfo, as
transcribed on Wikipedia) for every season the data fully covers, and fails on any difference.
All 19 seasons match exactly: positions, wins, losses, no results, points and net run rate to
three decimals. Wikipedia lists DC's 2025 net run rate as −0.011, but the scorecards give +0.011
(every other entry matches them exactly), so +0.011 is recorded. The tie-break was found the
same way: separating level teams by net run rate alone misorders 2015 and 2025; wins first, then
net run rate, reproduces every season.

**Limits:** the league stage only (playoffs have no table); finishes come from playoff results
(champion, runner-up, or the playoff match a side went out in).

## Home ground, close finishes and form

Team records are split by situation. Three of the splits need a definition:

- **Home ground.** A ground in India is a side's home in a season when the side played at least 2
  league matches there and was in at least 75% of the league matches played there. Seasons
  abroad or at shared neutral venues (2009, 2020–2022, the UAE leg of 2014) have no home sides,
  and adopted grounds count (Ranchi for CSK in 2014). Every match is home/away or neutral for
  both sides, never home for both. Home sides won 53.4% of 897 such matches (90%: 50.7–56.1%).
- **Close finish.** Won by 5 runs or fewer, with 2 balls or fewer to spare, or in a super over:
  17.8% of decided matches.
- **Form.** A side's results in its previous 14 matches (about a season), counting only matches
  before the one being described, shrunk toward an even record as if it had also played 80
  matches at 50%:

```
form(side)  = (wins in last 14 + 40) / (decided in last 14 + 80)
P(A beats B) = log5 = fA (1 − fB) / (fA (1 − fB) + fB (1 − fA))
```

**Why the shrinkage:** T20 results are noisy. On every IPL match since 2008, 80 is the strength
that predicts results best (log loss 0.6920, against 0.6931 for a coin flip); with less shrinkage
form predicts worse than a coin flip, and even at its best the side in better form wins 53.3% of
the time (expected 52.3%). An earlier version measured form from the same season with the match
left out; that biased the test (removing a win lowers the winner's form and raises the loser's,
so favourites appeared to underperform by 20 points), and form now counts only earlier matches.

## Head-to-head expectation

On the head-to-head page, A's wins over B are set against what both sides' form going into each
meeting predicts:

```
expected wins = Σ over decided meetings of log5(form A, form B)
chance range  = expected ± 1.645 · √Σ p (1 − p)
```

A record outside the range is outside what chance gives nine times in ten; with dozens of
rivalries a few land there by chance, so the page says so rather than calling it a hold.

**Validation** (Analytics Lab: [Do rivalries and close finishes repeat?](https://criciq-eight.vercel.app/lab/rivalries)):

- Sides that had won 60%+ of at least six earlier meetings won 53.4% of the next, against 51.0%
  expected from form: +2.4 points (90%: −1.3 to +6.6). Each extra 10 points of past dominance
  adds +1.2 points of win rate above form (90%: −2.6 to +5.5). Head-to-head history predicts
  nothing beyond form.
- The side in better form wins close finishes (52.7%, expected 52.5%) as often as other matches.
  A side's record in close finishes carries over to the next season with r = 0.11 (49 pairs of
  seasons with 3+ close finishes; shuffled seasons give ±0.25 nine times in ten), but so does
  little else: a side's whole win rate carries over with r = 0.06 across 149 pairs of seasons.
  The test rules out a large close-finish skill, not a small one.

**Limits:** form is results only, not the players available; the shrinkage was chosen on these
same matches (one number); a small rivalry or close-finish effect could hide inside the
intervals.

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
