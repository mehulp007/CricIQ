# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.0.0] - 2026-10-11

v2, "all of cricket": men's Tests, ODIs and T20Is and the IPL, BBL, CPL, PSL and SA20, each with its
own models. It runs on your machine (`just v2-up`, ADR-0016) from the `v2` branch; the hosted demo
stays v1.0.0, the IPL edition, on `main`.

### Added
- **V2-8: the local release** (ADR-0016)
  - `just v2-up` serves a production build of the web app: it starts the API, waits for its health
    check, builds the web app only when its sources changed since the last build, then serves it;
    it stops early, saying what to do, if a port is busy or no data has been built. `--dev` runs
    the Next.js dev server instead.
  - `scripts/perf.py` times every competition's key endpoints (cold and warm) and a 10,000-match
    simulation against the running API. Measured on a laptop: warm p95 median 50 ms, worst 178 ms
    (an ODI team page); simulations 0.5-0.6 s for the T20 competitions and 1.2 s for ODIs.
  - Lighthouse (mobile, throttled, production build): 92-95 performance on every competition's
    overview, replay, players, teams, Model Insights and series pages and the write-up; 100
    accessibility, best practices and SEO on all of them.
- **Series, tournaments and careers across formats** (V2-7, ADR-0015).
  - Data: Cricsheet's event group is extracted (`matches.event_group` in the full warehouse);
    the T20I, ODI and Test serving databases get `events`, `event_matches` and
    `event_standings` (`criciq_pipelines.events`), with major tournaments' names joined and
    edition round names in `config/events.yaml`. The export fails if any of 27 known results
    (every major tournament champion with its final in the data, complete Test series) comes
    out differently, and the full-data tests fail if any is not covered.
  - API: `/api/v2/{competition}/series` (filters by kind, year, side, major), `/series/{id}`
    (matches, tables, knockouts, top performers, win probability added) and `/series/h2h`;
    match details and timelines name their series; careers add innings, averages, hundreds and
    fifties, best scores and figures; `/api/v2/players/{id}/ratings` gives headline ratings in
    every competition.
  - Site: a Series section for Tests, ODIs and T20Is (major tournaments by edition, every
    series and tournament page), latest series on their home pages, series links on match
    pages, every format on the head-to-head page, career numbers and ratings in every
    competition on player pages, and Compare across competitions.
  - Analytics Lab notes across formats (`criciq-ml lab-formats`, run by `just publish-models`):
    "Does the toss matter more in Tests?" and "Home advantage by format"; every competition
    now has an Analytics Lab, and the IPL's own notes stay with the IPL.
- **Test cricket** (V2-6, ADR-0014): men's Tests from 2001 on every page under `/test/`.
  - Data: a Test copy of the warehouse (`test.duckdb`, with declarations, follow-ons, innings
    wins and the days played), `serving-test.duckdb` (each side's innings in the match summaries,
    "Match drawn" and innings victories in the results, draws in the team tables) and a `test`
    scope in the players database.
  - Win probability with three outcomes (win, draw, loss), a multinomial regression per innings
    the API can run (`criciq_core.test_win_probability`, `criciq_ml.test_match`): test log loss
    0.633 against 0.651 for the match state alone over 59 Tests (95% interval -0.045 to +0.074),
    better in 12 of 15 backtest years; boosted trees memorised matches (0.836 against 0.736 on
    the rolling origin) and are not used. The time left is estimated (five days of 90 overs less
    those bowled) and the cards say how approximate that is.
  - Every innings projected (mean miss 63 runs against 67 for par; 80% range holds 76.6%), the
    ball model with Test phases (0.9879 against 1.0005, 13 of 13 backtest years) and Test
    ratings (wicket-taking per 20 overs, the fourth innings, expected result added).
  - No match simulator: a fourth-innings chase what-if in the replay
    (`/matches/{id}/chase`) and a Chase calculator page (`/chase`, `/chase/sides`).
  - The Test replay: three-way result bar and chart, estimated day markers, projections in every
    innings, jumps by day and innings, speeds up to 64x; Test Model Insights; six featured Tests.
  - `just train-group test` trains the Test group (no simulator step).
- **Model groups: every kind of cricket modelled from its own matches** (ADR-0013)
  - `config/model_groups.yaml`: the IPL, the other leagues (BBL, CPL, PSL, SA20), men's T20
    internationals and ODIs each train on and serve their own competitions only, from their own
    warehouse copy (`leagues.duckdb` and `t20i.duckdb` are new, built by `run` and every sync).
    Training settings for the leagues and T20Is are in `config/models/leagues/` and
    `config/models/t20i/`, and the IPL's v1 settings, for retraining it, in `config/models/ipl/`.
  - `just train-group <group>` trains a group's five models in order, promotes what passes its
    gate, resumes an interrupted run and writes `data/training/<group>/summary.md`;
    `just publish-models` scores every competition and writes the cards, Model Insights data and
    featured replays; `just model-status` shows which models serve each group.
    `criciq-ml train|report --group <group>`.
  - The leagues' ratings borrow a thin component's shrinkage from the four leagues together,
    never from all T20.
  - Until a group's models are trained, its competitions keep the pooled T20 models, and scoring
    says so for each one.
  - **The leagues' and T20Is' own models**, trained on a laptop and tested once on 2025-2026.
    Leagues (1,563 matches): win probability 0.504 against 0.516 for the baseline (95% interval
    -0.001 to +0.024), projection 16.8 runs against 18.2 for par, ball model better in all 11
    backtest years, simulator served for the BBL, CPL and SA20. T20Is (3,480 matches): win
    probability 0.432 against 0.458 (+0.017 to +0.034), projection 18.1 runs against 22.2, ball
    model better in all 11 years; the simulator is not served (totals 8 runs short).
  - **The T20I simulator is served** (1.1.0), and the PSL's: the simulator can follow the
    competition's recent scoring level (the scoring era moved so the ball model's expected runs
    over a window of previous matches equal the runs scored; the window, or none, chosen on the
    validation years) and choose the conditions spread by the validation PIT. T20Is: 152.0
    simulated against 153.8, PIT chi-square 6.5 (70.9 before); leagues: BBL 7.0, CPL 14.9, PSL
    10.4 (18.9 before), SA20 4.2. Scoring publishes each match's level (`sim_level_shifts`) and
    the API applies it.
  - The simulator's Model Insights says "ten-over quota" for ODIs (it said four).
  - The leagues' win probability 1.1.0 leaves out the squads' and crease batters' records,
    chosen on the pre-test years: with league-only careers they made the first innings worse.
  - Model Insights for the leagues and T20Is show their own models, each league's results, and
    the trade-off against the pooled model they replaced; the About page and the replay's
    explanation describe the groups.
- **V2-5: men's ODIs** (ADR-0012)
  - ODIs in the switcher with every page: replays over 50 overs (rain-revised chases use their
    revised target and overs), teams with records by year and by opponent, players with an ODI
    tab, matchups, compare, the simulator and Model Insights. Featured replays: every World Cup
    final since 2003, the Champions Trophy finals and South Africa's 435 chase.
  - ODI models of their own, trained on ODIs alone (`data/warehouse/odi.duckdb`, 2,576 matches
    from 2002) with the T20 models' features and protocols, tested once on 2025-2026 (174
    matches). Win probability: log loss 0.550 against 0.552 for the logistic baseline, ahead but
    with a 95% interval that includes no gain (better in 6 of 11 backtest years). Score
    projection: median error 31.2 runs against 38.0 for par, 80% range holding 82.6%. Ball
    outcome: 1.2076 against 1.2210, better in all 11 backtest years. CricIQ Ratings: the shrunk
    record beats the raw one for all 16 components. Forward selection on the pre-test years
    chose the batters at the crease for chases and the projection.
  - The simulator plays 50 overs with ten overs a bowler (`FormatRules`), and its ODI backtest
    passed: first-innings PIT chi-square 14.0 against 16.9, 88.7% of totals inside the 80%
    range, 10,000 matches in about a second. Before a ball is bowled it picks the winner no
    better than a coin flip (Brier 0.242 against 0.250), as in T20.
  - `criciq-ml train <model> --format ODI` and `report --format ODI`; the ODI models, configs,
    cards and Model Insights data live in `odi/` folders beside the T20 ones.
- **V2-4: every T20 competition on the site** (ADR-0011)
  - A competition switcher in the top bar (IPL, BBL, PSL, CPL, SA20, T20I, with ODI and Test shown
    as coming), remembered in a cookie, and a home page that leads with the choice. Every data page
    lives under `/[competition]/` (`/ipl/matches`, `/t20i/players/[id]`), and the v1 URLs redirect
    permanently (308) to `/ipl/...`.
  - One serving database per competition (`serving.duckdb` for the IPL,
    `serving-<competition>.duckdb` for the others), exported by `export`, `run` and every sync,
    scored with the models serving each competition, and published together.
  - `/api/v2/{competition}/...` for matches, replays, teams, matchups, the simulator and the
    Player Lab; `/api/v2/competitions` describes what each competition has. Response caches are
    bounded (least recently used) and keyed by competition.
  - National sides: team pages with records by year and by opponent instead of league tables, and
    a side is at home in its own country. Player pages have a tab for every competition a player
    played in and for all T20.
  - Featured replays for every competition (the T20 World Cup finals for T20Is), the replay's charts
    read the overs from the match, and Model Insights shows the pooled models' results for each
    competition (the Analytics Lab stays with the IPL).
  - The ball-outcome model 2.1.0 adds the batting and bowling side's level in internationals, so a
    player with few balls starts from their side rather than the average player: T20I log loss
    1.4430 against 2.0.0's 1.4470. It serves every competition except the IPL, which keeps 1.0.0.
  - The simulator 2.1.0 is backtested on each competition on its own 2025-2026 matches and serves
    each one whose backtest passes: the BBL, CPL and SA20 (first-innings PIT chi-square 6.8, 8.3
    and 7.7 against 16.9). For T20Is its pick of the winner is now better than a coin flip (Brier
    0.173 against 0.250) but its totals still run 7 runs low, and the PSL's run 10 low, so neither
    is served and each simulator page says why.
- **V2-3: pooled T20 models** (ADR-0010)
  - Win probability, score projection and the ball-outcome model 2.0.0 train on every T20
    competition at once (6,391 matches, `data/warehouse/t20.duckdb`), with splits by calendar year.
    Players carry one record across competitions; each competition keeps its own scoring era and
    chase tables. Forward selection on the pre-test rolling origin added the squads' and the
    batters' career records and an international-cricket flag. Ratios are rounded so every CPU
    agrees.
  - Each pooled model is compared with v1 on the IPL's own 2025-26 test balls (v1's predictions
    rebuilt exactly). Pooling does not help the IPL: win probability 0.524 against v1's 0.510,
    the ball model 1.4922 against 1.4895, and the projection's 80% range covers 86% of IPL totals
    (outside the 75-85% band). The IPL keeps v1 (`models/<name>/CURRENT.IPL`); the pooled models
    serve the BBL, PSL, CPL, SA20 and T20Is and beat their baselines in every competition.
  - CricIQ Ratings 2.0.0 are fitted for every competition and all T20 on their own records (small
    competitions borrow the all-T20 shrinkage); the players database gets win probability added and
    each scope's rating constants, and `/api/v2/{competition}/players/{id}/similar` serves similar
    players. The IPL's constants are unchanged.
  - The simulator 2.0.0 was backtested on T20Is with the pooled ball model and failed its gate
    (first-innings totals 7 runs low, PIT chi-square 37.4 against 16.9; win chances too close to
    even between unequal sides), so it is not served and every competition keeps 1.0.0. The
    simulator card publishes that backtest under "Backtested, not served".
  - Model cards and Model Insights data per competition: `docs/model-cards/<model>.md` for the
    pooled versions (results by competition, against v1 on the IPL) and `<model>-ipl.md` for the
    IPL's; `frontend/data/models/t20/` for V2-4. A "teams" explanation factor for the new features.
  - `criciq-data export-competition`, and the ball model's independent fits run in parallel.
- **V2-2: the T20 world** (ADR-0009)
  - A players database (`data/exports/players.duckdb`, `criciq-data export-players`) with the Player
    Lab tables of the IPL, BBL, PSL, CPL, SA20 and men's T20Is, and of all T20 cricket together. Par
    is each competition's own rate for the season and phase, so a PSL strike rate is judged against
    the PSL; the IPL's tables are identical to the serving database's. `run` and every sync build it.
  - `/api/v2/competitions` (with season names such as "2023/24" for the BBL),
    `/api/v2/{competition}/players`, `/players/{id}` and `/players/{id}/splits` for any T20
    competition or `t20`, and `/api/v2/players/{id}` with a player's line in every competition.
  - A data-quality report per T20 competition (`docs/data-quality/`): coverage by season, every check
    with the matches behind its notes, golden scorecards, teams with attribute coverage, quarantined
    matches and grounds added automatically.
  - Batting hand, bowling style and biography for 5,417 more players from Wikidata and Wikipedia
    (`enrich-players` now covers every competition, keeps existing rows unless `--refresh`, tries
    alternate ESPNcricinfo ids and retries dropped requests).
  - Golden scorecards for the PSL 2023 and CPL 2023 finals, and both matches as fixtures.
- **V2-1: incremental sync** (ADR-0008)
  - `criciq-data sync` takes in only what Cricsheet changed: it picks the 7-day, 30-day or full feed
    by the time since the last sync, compares every match file with an ingest log (new, corrected,
    withdrawn), applies those changes, then rebuilds, validates, exports and scores in staging so a
    failed sync changes nothing.
  - Matches that cannot be built or fail validation are quarantined with the reason while the rest
    go in; a bad correction keeps the previous version; `--retry-quarantined` tries them again.
  - `criciq-data sync-status`, `just sync`, `just sync-status`, and `scripts/sync_task.ps1` to run
    the sync every six hours with Windows Task Scheduler.
  - The site shows how fresh the data is ("Data updated 6 Oct 2026 · 2 new matches") and leads the
    overview with the latest matches; `/api/v1/meta` reports `last_update` and `latest_match_date`.
  - `.github/workflows/data-sync.yml` for a hosted v2 (switched off; removed in 2.0.0, since v2
    runs locally).
- **V2-0: multi-competition foundation**
  - One warehouse for every competition (ADR-0007): the IPL, BBL, PSL, CPL and SA20, and men's
    T20Is, ODIs and Tests, about 9,900 matches and 4.6 million deliveries, registered in
    `config/competitions.yaml` and classified from each match's own details.
  - Test cricket in the data model: draws, wins by an innings, declarations, forfeits, follow-ons,
    penalty runs and match days; ODI and open-ended Test phases.
  - Teams across formats (`config/teams/`), national sides with one identity, seasons from
    Cricsheet labels or the calendar, grounds added automatically with countries, a quarantine for
    source errors, and format-aware validation with notes for quirks outside curated competitions.
  - Seven new golden scorecards (the 2019 World Cup final, the 2005 Edgbaston Test, Adelaide 2020,
    Sydney 2021, the 2016 World T20 final, BBL and SA20 finals) and 17 new fixture matches.
  - An IPL regression gate: the IPL warehouse and scored serving database are compared table by
    table with checksums from the v1 code.
  - The data-quality report covers every competition.
  - Innings phases follow each match's format: data code phases T20, ODI and Test deliveries by
    their own format, and the T20 models refuse a database holding other formats instead of scoring
    them with T20 phases.
  - `just v2-up`: the local v2 runtime builds every competition, scores every ball and serves the
    API and the web app together.

### Changed
- **V2-8:**
  - Charts load after the page paints (`next/dynamic`): the charting library left the first
    JavaScript of the teams, team, replay, player, Model Insights and write-up pages, which took
    the slowest pages from 70-85 to 92 and above in Lighthouse.
  - Each database's DuckDB buffer pool is capped (`CRICIQ_DUCKDB_MEMORY_LIMIT`, default 384 MB)
    where DuckDB allowed each of the nine up to 80% of RAM; the API holds about 0.9 GB with every
    competition loaded.
  - Versions are 2.0.0 across the Python packages, the web app and the OpenAPI document.
- **The write-up** (`/writeup`) tells the v2 story: the data of all eight competitions, the five
  model groups and the price of training each on its own matches (own against pooled T20 win
  probability), every group's win probability, projection and simulator against their baselines,
  Test cricket's models, and the incremental sync. Its tables read the published model data.
- **V2-5:** the format is a context (`criciq_core.phases.use_format`) that the models, the chase
  table, the projection's baseline, the rating components and the registry read; the simulator's
  overs, quota and phases travel with each side. T20 output is unchanged. The players database
  has an ODI scope after All T20, and player pages list every competition.
- **V2-4:** `/api/v1` is retired on the v2 branch (it stays on `main`, the hosted IPL edition), and every
  page, API client function and route handler takes the competition. The `meta` table records
  whether seasons span the new year, so the BBL's read "2025/26".
- Teams without curated colours (some league sides) get a neutral grey everywhere.
- The running API swaps in a newly published serving database between requests, and new data
  waits beside the open file (`serving.duckdb.next`) instead of failing to replace it on Windows.
  `criciq-ml score` scores one working copy and puts it in place once at the end.
- The web app keys its cached API responses by the data version and re-reads it every five
  minutes, so new data shows within minutes rather than after the day-long cache.
- The API image fetches Cricsheet's files with `ADD`, so a changed archive rebuilds the data layer
  instead of shipping a cached copy.
- `criciq-data download` and `run` fetch every selected competition (`CRICIQ_COMPETITIONS`, default
  all); `snapshot` takes several archives. The API image builds the IPL only.
- `config/franchises.yaml` moved to `config/teams/ipl.yaml`.

### Removed
- `.github/workflows/data-sync.yml`: the cloud sync was for a hosted v2. The sync runs locally
  (`just sync`, scheduled with `scripts/sync_task.ps1`).

### Fixed
- **V2-5:**
  - A super over that was itself tied, settled on boundaries (the 2019 World Cup final, IPL 2014
    KKR v RR), read "won the super over"; it now says so.
  - The replay's what-if played a rain-revised chase over its full overs instead of its revised
    allocation.
  - Under `/[competition]/`, only the featured replays opened: every other match page was a 404
    (since V2-4). The competition layout turns dynamic params off, Next applies that to the whole
    route, and the match page listed only the featured replays as its params; it now lists none,
    like the player and team pages.
- **V2-4:**
  - A tie with no winner had no result text, and a match settled by a bowl-out said "won the
    super over"; they now read "Match tied" and "won the bowl-out".
  - Home and away counted only grounds in India, so league sides elsewhere had no home matches:
    a league side's home is the ground it played most of its league matches at that season (in
    India for the IPL), and a national side's is its own country.
  - The Analytics Lab read the ball model serving the other competitions instead of the IPL's.
  - The pressure on a replay's next ball crashed with the pooled models (two crease features were
    not carried between balls), and the check of leverage against the swings that followed
    depended on row order.
  - A replay's explanation said team records were not used even where the model uses them.
  - League tables outside the IPL were checked against the IPL's official tables.
- A chase without a recorded target (23 T20Is, a CPL match) chases the first-innings total plus one
  in the models, and a T20 recorded as a 50-over match (11 T20Is) lasts 20 overs; the new check
  `scheduled_overs_within_format` lists those matches in the data-quality reports.
- The players loading skeleton gave two placeholders the same key.
- The simulator failed on a side that names twelve under supersub rules (two 2026 T20Is); it now
  bats the eleven who usually bat highest.
- Fifteen grounds recorded under former or sponsors' names (Launceston's Aurora Stadium, Bloemfontein's
  four names, Rajkot's Niranjan Shah Stadium and others) are merged, and a sponsor's name for a
  ground whose plain name several grounds share resolves by city.
- An over split between two bowlers (three balls each) is credited to the bowler who started it;
  before, the choice depended on row order.
- Grounds that share a name are told apart by city: Karachi's National Stadium (about 150 matches)
  had been filed under Bermuda's, and Nehru Stadiums and County Grounds in different cities had been
  merged. Eighteen grounds recorded under two names (sponsors' names and spellings) are merged.
- `/api/v1/meta` reports the versions of the models that scored the data (it always returned none).
- `criciq-data report` and `run` write the data-quality report with LF line endings on Windows.

## [1.0.0] - 2026-10-05

V1: every planned feature is live (milestones V1-a to V1-d), plus a release pass.

### Added
- **Release pass**
  - Model Insights overview (now the default tab): every model against its baseline on the test
    seasons in plain words, a chart of the seasons each model learned from, was tuned on and was
    tested on, the testing rules, the custom metrics' tests and the model registry.
  - The write-up (`/writeup`, in the sidebar): how CricIQ was built and tested, what failed and
    what comes next, with its numbers read from the model registry.
  - Version 1.0.0 across the Python packages, the API and the web app.
- **Simulator seasons and squads:** pick any season from 2008 to 2026, two sides that played in
  it, and each XI from that side's squad that season (everyone who played for it, with their
  appearances; the season's last XI by default). The match is played in that season's scoring
  era, with league rates and players' batting positions and bowling usage as of then; players
  from outside the squad are refused. `GET /simulate/seasons`, `GET /simulate/squad/{season}/{team}`
  and `season` on `POST /simulate/match`.
- **V1-d: match simulator and what-if sandbox**
  - `criciq_core.simulation`: a vectorised Monte Carlo engine that plays matches ball by ball with
    the ball-outcome model, league extras and run-out rates, a usage-based bowling policy that
    respects the quota and never strands an innings, and per-match conditions shared by both
    innings (ADR-0006: numpy in the API).
  - Match Simulator (`/simulator`): any two XIs (each team's latest by default; reorder, swap
    players, choose bowling options and who bats first), 10,000 simulations in half a second on a laptop,
    with win shares, first-innings distributions, the average simulated scorecard and margins.
  - What-if sandbox in every replay: edit the runs or wickets at any ball and see the batting
    side's chance, anchored on the win probability model and moved by the simulated change, with
    the projected total.
  - `criciq-ml train simulator`: tunes the conditions spread on 2023-2024 and backtests every
    2025-2026 match pre-match (Brier against a coin flip, form and the batting-first rate; PIT
    and coverage of first-innings totals; chases from the first ball), with a model card and a
    Simulator tab on Model Insights.
  - `GET /simulate/xi/{team}`, `POST /simulate/xi`, `POST /simulate/match`, `POST /simulate/state`;
    tables `bowling_usage` and `sim_league_rates`.
- **V1-c: team analytics and head-to-head**
  - League tables for every season rebuilt from the scorecards (points, wins, net run rate under
    the playing conditions' rules, abandoned fixtures, playoff finishes); the export fails unless
    they match the official tables, and all 19 seasons do.
  - Teams page (`/teams`): every franchise under every name, any season's table and playoffs,
    champions, and what chasing, the home ground and the toss are worth, with 90% intervals.
  - Franchise pages (`/teams/[id]`): season by season, results by situation (batting order, toss,
    home or away, stage, close finishes), batting and bowling by phase against par, totals and
    margins, leading players, record against each opponent and at each ground, and the greatest
    comebacks and costliest defeats by win probability, each linked to the replay.
  - Head to head (`/teams/h2h`): any two franchises by season, ground, batting order and stage,
    their highest totals and leading players, every meeting, and the record set against what
    each side's form predicted.
  - Analytics Lab note "Do rivalries and close finishes repeat?": head-to-head history and
    close-finish records predict nothing beyond form, and form itself barely predicts results.
  - `GET /teams`, `/teams/standings/{season}`, `/teams/{id}`, `/teams/h2h`; tables
    `team_matches`, `team_innings_phases`, `team_season_records`; `config/league_tables.yaml`.
- **V1-b: pressure, momentum and the Analytics Lab**
  - Pressure on the next ball in every replay: leverage from what-if win probabilities for each
    possible outcome (smoothed over nearby scores), its 0-100 percentile and band, a pressure
    chart on a log scale and the tensest moments so far. Validated: expected and realised
    next-ball swings agree in every tenth of leverage.
  - Momentum in every replay: each side's win probability gained over the last 12 legal balls.
  - Analytics Lab (`/lab`): research notes on momentum (descriptive, not predictive), pressure
    (batters take more risk at the end of close chases) and clutch (not a reliable skill, so not
    rated), with match-level bootstrap intervals and a permutation test, generated by
    `criciq-ml report` and bundled.
  - Timeline fields `leverage`, `pressure`, `momentum` (and `*_start`), and the pressure bands in
    leverage units on the win probability model.
- **V1-a: Compare, CricIQ Ratings and similar players**
  - CricIQ Ratings on every profile, replacing the raw percentiles: 8 batting and 8 bowling
    components against par (run scoring, survival, each phase, chasing or defending, impact,
    consistency, economy, wicket-taking), each shrunk towards the qualified average by an
    empirically fitted amount and shown as a 0-100 rating with a 90% interval. Low-stability
    components are flagged.
  - `criciq-ml train ratings`: tunes the shrinkage per component on next-season prediction,
    tests it on 2023-2026, and reports year-to-year and odd/even-season stability; committed
    under `models/ratings/` with a model card and a Ratings tab on Model Insights.
  - Similar players on every profile: z-scored style profiles compared by cosine similarity,
    with shared traits and a one-click comparison; validated by a retrieval test.
  - Compare page (`/compare`): any two players over the same seasons, side by side against par,
    ratings on shared tracks, season-by-season form by year or by age, phases and their
    head-to-head.
  - `GET /players/{id}/similar`; `player_batting_phases` and `player_bowling_phases` tables.
  - `docs/metrics.md`: par, win probability added, ratings and similar players, with formulas.

### Changed
- The simulated scorecard shows each player's typical (median) innings in whole runs, balls and
  wickets, with the middle half of their scores as a range, instead of fractional averages.
- The simulator and the replay's what-if retry while a sleeping API wakes (the free instance
  sleeps when idle), start waking it as soon as either page opens, and say so instead of failing;
  the API builds the simulator and plays a few matches at startup.
- The what-if takes players' batting positions and bowling usage as of the match's season.
- README: a demo GIF touring every section, a more detailed architecture section, and no roadmap
  (every milestone is done; this changelog records them).

### Removed
- The "Build progress" list on the Overview page.

## [0.1.0] - 2026-10-01

The MVP: milestones M0 to M6, plus a release pass.

### Added
- **Release pass**
  - Overview: the latest season at a glance (champion, scoring, leaders against par) and the
    biggest win-probability swings in IPL history, both bundled so the page never waits for the API.
  - About & Methodology rewritten to cover the data, all three models, par, win probability added,
    matchup shrinkage, engineering and limitations, with figures read from the model registry.
  - Accessibility: an axe-core WCAG 2.1 A/AA scan of every key page in the end-to-end suite;
    scrollable tables are keyboard-focusable and labelled; loading skeletons announce themselves.
  - Open Graph image and metadata, `robots.txt` and a sitemap.
  - Lighthouse audit of the key pages (mobile and desktop) recorded in the README.
- **M6 Matchup Lab and ball-outcome model**
  - `criciq_ml.ball_outcome`: multinomial logistic regression over seven outcomes per ball faced,
    with situation terms, the scoring era and ridge-penalised batter and bowler effects. Tested on
    2025–2026: log loss 1.4895 vs 1.5057 for phase-and-wickets
    frequencies (1.07% better; players add 0.33% over the situation alone), better
    than the baseline in 11 of 11 backtest seasons, per-outcome calibration reported.
  - Head-to-head shrinkage: a Dirichlet prior centred on the model's expectation for each pair's
    balls, with strength fitted by empirical Bayes (355 balls), validated on future balls.
  - `criciq-ml train ball_outcome`; scoring publishes head-to-head cells and the model's terms.
  - API: `GET /matchups`, `GET /matchups/{batter}/{bowler}` and `POST /predict/next-ball`,
    computed from the stored terms with no ML library (ADR-0005).
  - Web: Matchup Lab with player search, rivalry lists, the three readings of a record with 90%
    intervals, next-ball odds by phase; most-faced opponents on player profiles; a Ball outcome
    tab in Model Insights.
- **M5 Player Lab**
  - `criciq_pipelines.players`: serving tables for batting and bowling innings (with match context
    and batting position), ball-level cells by season, phase and opponent type, league par rates,
    fielding, player seasons and a searchable directory with derived roles.
  - Par: every innings and cell carries the runs, dismissals, dots and boundaries an average player
    would have produced from the same balls (league rate for the same season and phase).
  - Win probability added per player and innings, published by `criciq-ml score`.
  - API: `GET /players` (search, role, season, team, sort), `GET /players/{id}` (career or season
    window: summaries against par, seasons, phases, percentiles, recent form, dismissals) and
    `GET /players/{id}/splits`.
  - Web: Player Lab directory with search and filters, and profile pages with batting and bowling
    tabs, a season-window control, percentile bars, season charts, splits and recent form.
    Scorecard names link to profiles.
- **M4 Score projection**
  - `criciq_ml.projection`: LightGBM quantile models (5–95%) of the first-innings total, predicted
    as a ratio to the scoring era's par so one model spans 2008–2026, with per-level conformal
    calibration and a piecewise-linear CDF for P(total ≥ X).
  - Protocol: tune on 2021–2022, calibrate on 2023–2024, test on 2025–2026 (no season does two
    jobs), rolling-origin feature selection and a season-by-season backtest that doubles as the
    season-bias check. Test: 80% range covers 80.3%, median error 16.9 runs vs
    18.4 for par and 27.9 for the run-rate projection.
  - `criciq-ml train score_projection`, a promotion gate on coverage and error, a generated model
    card, and projections scored into the serving database with the win probabilities.
  - API: first-innings timelines carry projection quantiles. The `models` table is now generic.
  - Replay: projected-total panel with the odds of passing round totals, and a projection fan on
    the worm chart. Model Insights gains a Score projection tab.
- **M3 Win probability**
  - `criciq_ml`: leak-free, as-of match-state features (tested by deleting and rewriting later
    matches), a WASP-style chase dynamic programme, and two monotonic LightGBM models.
  - Evaluation protocol: tuning on 2023-2024, calibration and feature selection by rolling origin on
    pre-test seasons, one-shot test on 2025-2026, a season-by-season backtest and a match-level
    bootstrap against a logistic baseline and a state-only model. Test log loss 0.510 vs 0.549.
  - TreeSHAP explanations grouped into cricket concepts and converted to percentage points.
  - Versioned model registry committed under `models/`, with a promotion gate and a generated model
    card (`docs/model-cards/win-probability.md`). ADR-0004.
  - `criciq-ml` CLI (`train`, `score`, `report`). The API image scores every ball at build time, and
    the API serves precomputed probabilities with no ML libraries.
  - Replay: win probability bar, win probability chart with turning points, "Why this estimate"
    panel, per-ball swings in the commentary, and deep links to any ball (`?ball=innings.seq`).
  - Model Insights page: calibration, backtest, comparisons, rejected features, calibration choice
    and the biggest swings in IPL history.
  - Notebook `02_wp_experiments`: LightGBM vs XGBoost vs CatBoost, the chase feature, the 2019 final.
- **M2 Match Explorer & Replay (first public deployment)**
  - Live at https://criciq-eight.vercel.app (web on Vercel, API on Render).
  - API: `GET /api/v1/matches` (filters, pagination), `/matches/{id}` (full scorecards) and
    `/matches/{id}/timeline` (one payload per replay), all cacheable and gzip-compressed.
  - `criciq-data export`: slim read-only serving database with match summaries. Extraction now streams
    (peak memory 375 MB to 50 MB).
  - Match Explorer with season, team and playoff filters.
  - Match Center: live scoreboard, crease panel, commentary with Impact Player events, worm and
    Manhattan charts, live scorecard, play/step/seek/speed controls and keyboard shortcuts.
  - Featured replays bundled with the web app; honest "engine warming up" state for API cold starts.
  - Typed API client generated from the OpenAPI spec, with a drift test.
  - Playwright end-to-end tests (desktop and mobile), plus CI jobs for e2e and the API Docker image.
  - Docs: deployment guide, ADR-0003 (hosting), README demo GIF and screenshots.
- **M1 Data warehouse**
  - Content-addressed raw snapshots of Cricsheet's IPL archive and people register (`criciq-data download`).
  - Extraction of every match into typed Parquet tables, resolving people by registry id and counting legal balls.
  - Normalized DuckDB warehouse with enforced keys, references and domains: competitions, seasons, franchises, team seasons, venues, players, matches, innings, deliveries, wickets, squads and substitutions.
  - Reference config for franchise renames, venue aliases and competition rules.
  - 17 SQL invariant checks and 6 golden scorecards, with a generated data-quality report.
  - Player attributes (full name, date of birth, country, batting hand, bowling style) from Wikidata and Wikipedia, with documented overrides.
  - `criciq-data run`: one-command rebuild from download to validated warehouse and report.
  - 14 real-match test fixtures covering every data edge case; negative tests prove the checks catch corruption.
  - EDA notebook linking data findings to modelling decisions; docs for the pipeline and data dictionary.
- **M0 Foundations**
  - uv workspace (Python 3.12) with `core`, `pipelines`, `ml` and `backend` packages.
  - `criciq_core`: overs/run-rate arithmetic on legal balls and configurable innings phases (`config/phases.yaml`).
  - `criciq-data` CLI skeleton (`paths` command).
  - FastAPI app with `/healthz` and versioned `/api/v1/meta`.
  - Next.js 16 frontend: "floodlit night match" design tokens, responsive app shell with sidebar and mobile drawer, Overview and About & Methodology pages.
  - Tooling: ruff, mypy (strict), pytest, Vitest and Testing Library, Prettier, pre-commit, `justfile`.
  - GitHub Actions CI for Python and frontend.
  - Docs: engineering plan, architecture overview, ADR-0001 (DuckDB), ADR-0002 (uv workspace on Python 3.12).
