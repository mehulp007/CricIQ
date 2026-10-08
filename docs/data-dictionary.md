# Data Dictionary

Tables in the CricIQ warehouse. `data/warehouse/cricket.duckdb` holds every competition; the
sections below describe the IPL copy (`data/warehouse/ipl.duckdb`, the v1 shape the export and the
models read), and [Every competition](#every-competition-cricketduckdb) lists what the full
warehouse adds. The authoritative DDL, with every constraint, is
[`schema.sql`](../pipelines/src/criciq_pipelines/sql/schema.sql). Core entities are
format-agnostic; competition-specific knowledge lives in `config/`.

**Conventions**
- Players, officials and substitutes are identified by their Cricsheet person id (8 hex chars).
- `over_no` is 0-based, as in Cricsheet. Phase and display code converts to 1-based overs.
- "Legal ball" means any delivery that is not a wide or a no-ball.
- Team references point to **`team_seasons`** (a franchise in a given season), never to raw names.

## Reference

### `competitions`
| Column | Meaning |
|---|---|
| `competition_id` | e.g. `IPL` |
| `name`, `short_name` | Display names |
| `format` | `T20` (later `ODI`, `Test`) |
| `gender`, `team_type` | `male`, `club` |

### `seasons`
| Column | Meaning |
|---|---|
| `season_id` | `IPL-2008` … |
| `year` | Calendar year of the season's matches |
| `cricsheet_label` | Cricsheet's label (e.g. `2007/08` for 2008, `2020/21` for 2020) |
| `impact_player_rule` | Whether Impact Player substitutions were allowed |

### `franchises`
| Column | Meaning |
|---|---|
| `franchise_id` | Stable id: `CSK`, `DC`, `GT`, `KKR`, `LSG`, `MI`, `PBKS`, `RCB`, `RR`, `SRH`, defunct `DCH`, `GL`, `KTK`, `PWI`, `RPS` |
| `name` | Current (or final) name |
| `primary_color`, `secondary_color` | Data-accent colours for the UI |
| `first_season`, `last_season`, `is_active` | Lifetime |

### `team_seasons`
| Column | Meaning |
|---|---|
| `team_season_id` | `<franchise_id>-<year>`, e.g. `DC-2012` |
| `franchise_id`, `season_id` | Parents |
| `display_name` | Name used that season, e.g. `Delhi Daredevils` |

### `venues` / `venue_aliases`
| Column | Meaning |
|---|---|
| `venue_id` | Slug for a physical ground, e.g. `chinnaswamy` |
| `name`, `city`, `country`, `notes` | Canonical description, including rename history |
| `venue_aliases.raw_name` → `venue_id` | Every raw Cricsheet venue string (a name several grounds share, told apart by city, maps to each of them) |

### `players`
| Column | Meaning |
|---|---|
| `player_id` | Cricsheet person id |
| `name` | Cricsheet scorecard name, e.g. `V Kohli` |
| `unique_name` | Cricsheet's disambiguated name |
| `full_name` | Commonly used full name, e.g. `Virat Kohli` (Wikidata/Wikipedia) |
| `date_of_birth`, `country` | Country is the international side represented (drives overseas status) |
| `batting_hand` | `right` / `left` |
| `bowling_arm`, `bowling_type`, `bowling_style` | `right`/`left`, `pace`/`spin`, e.g. `Right-arm fast-medium` (primary style) |
| `attributes_source` | Provenance: Wikidata QID, Wikipedia title, `manual` |

Missing attributes are `NULL`, never guessed.

### `player_identifiers`
`(player_id, source, value)` maps each player to external ids from Cricsheet's register
(`cricinfo`, `cricbuzz`, `bcci`, …).

## Matches

### `matches`
| Column | Meaning |
|---|---|
| `match_id` | Cricsheet match id |
| `season_id`, `competition_id` | Parents |
| `match_order` | Strict chronological ordinal (date, match number, id). **The key for as-of features** |
| `match_date`, `end_date` | Differ when a match used a reserve day |
| `match_number`, `stage`, `is_playoff` | League number, or stage such as `Final`, `Qualifier 1` |
| `venue_id` | Canonical ground |
| `team1_id`, `team2_id` | Team seasons, in Cricsheet's listed order (not batting order) |
| `toss_winner_id`, `toss_decision` | `bat` / `field` |
| `outcome_type` | `win`, `tie`, `no_result` |
| `winner_id` | Winner; for a tie, the side that won the super over |
| `win_by_runs`, `win_by_wickets` | Margin. Under D/L a chasing side can win "by runs" (ahead of par) |
| `win_method` | `D/L` when a rain rule decided the result |
| `decided_by_super_over` | Tie settled by one or more super overs |
| `scheduled_overs`, `balls_per_over` | 20 and 6 for the IPL |
| `player_of_match_ids` | List of player ids |

### `innings`
| Column | Meaning |
|---|---|
| `(match_id, innings_no)` | Key; super overs continue the numbering (3, 4, …) |
| `batting_team_id`, `bowling_team_id` | Team seasons |
| `is_super_over` | Super-over innings are excluded from models |
| `target_runs`, `target_overs`, `target_balls` | Chase target; revised under D/L (e.g. 9.2 overs = 56 balls) |
| `runs`, `wickets`, `legal_balls`, `extras` | Totals. Wickets count dismissals only (retired hurt excluded) |
| `absent_hurt_ids` | Batters unable to bat |
| `miscounted_overs` | Cricsheet's record of umpire-miscounted overs (JSON, 0-based over keys) |

### `deliveries`
One row per delivery, including wides and no-balls.

| Column | Meaning |
|---|---|
| `(match_id, innings_no, seq_no)` | Key; `seq_no` is the delivery's position in the innings |
| `over_no`, `ball_label` | 0-based over; Cricsheet's `over.ball` label (repeats on wides) |
| `legal_ball_no`, `is_legal` | Legal balls bowled so far in the innings, including this delivery |
| `batting_team_id`, `bowling_team_id` | Team seasons |
| `batter_id`, `non_striker_id`, `bowler_id` | Players |
| `runs_batter`, `runs_extras`, `runs_total` | `runs_total = runs_batter + runs_extras` (enforced) |
| `is_four`, `is_six` | True boundaries only (fours that were run are excluded) |
| `extras_wides`, `extras_noballs`, `extras_byes`, `extras_legbyes`, `extras_penalty` | Extras breakdown |
| `is_wicket` | A dismissal happened on this delivery (retired hurt excluded) |
| `team_runs`, `team_wickets` | Running score **after** this delivery |
| `has_review` | A DRS review was taken |

### `wickets`
| Column | Meaning |
|---|---|
| `(match_id, innings_no, seq_no, wicket_no)` | Key |
| `player_out_id`, `kind` | e.g. `caught`, `run out`, `retired hurt` |
| `is_dismissal` | False for `retired hurt` (the batter may return) |
| `bowler_credited` | Bowled, caught, c&b, lbw, stumped, hit wicket |
| `bowler_id` | Bowler of the delivery |
| `fielder_ids`, `fielder_is_substitute` | Parallel lists |

### `match_players`
| Column | Meaning |
|---|---|
| `(match_id, player_id)` | Key |
| `team_season_id`, `list_position` | Side and order in Cricsheet's team list |
| `selection` | `playing_xi`, `impact_substitute`, `concussion_substitute` |
| `substituted_out` | Replaced during the match |

### `substitutions`
| Column | Meaning |
|---|---|
| `(match_id, innings_no, seq_no, sub_no)` | When it happened |
| `kind` | `match` (player swap) or `role` (e.g. a bowler replaced mid-over) |
| `reason` | `impact_player`, `concussion_substitute`, `injury`, … |
| `team_season_id`, `player_in_id`, `player_out_id`, `role` | Details |

## Every competition (`cricket.duckdb`)

The full warehouse has the tables above for every competition, with these differences. The IPL copy
is built from it by `criciq_pipelines.scope`, which keeps only v1 columns and calls teams
`franchises`.

| Table | Difference |
|---|---|
| `competitions` | `format` is `T20`, `ODI` or `Test`; `team_type` is `club` or `national`; `switcher` marks competitions in the site's switcher (IPL, T20I, ODI, Test) |
| `seasons` | `season_id` is `<competition>-<year>`; `start_date` and `end_date` of the season's matches. Label seasons take the year they end (BBL 2023/24 is 2024); calendar seasons the year of the first day |
| `teams` | One identity across seasons and, for national sides, formats: `team_id` (`MI`, `SYS`, `IND`), `name`, `team_type`, optional colours, `is_curated` (false for a side added automatically) |
| `competition_teams` | Which teams a competition has: `first_season`, `last_season`, `is_active` (a national side is active if it played in the competition's last three seasons) |
| `team_seasons` | `team_id` instead of `franchise_id`. Club ids stay `<team>-<year>`; national ids carry the competition (`ODI-IND-2023`) |
| `venues` | `is_curated`; `city` and `country` can be NULL for an added ground |
| `venue_aliases` | `is_curated`: false for raw names mapped automatically |
| `matches` | `match_order` is chronological within a competition and `global_order` across all; `outcome_type` adds `draw`; `win_by_innings`; `decided_by_bowl_out`; `scheduled_overs` is NULL for Tests; `days`; Cricsheet's `event_name` (series or tournament) and `match_type_number`; `has_supersubs` (the 2005-06 twelve-player rule) |
| `innings` | `declared`, `forfeited`, `follow_on` (the side bats twice in a row), `penalty_runs` (awarded outside the deliveries and included in `runs`) |
| `auto_added` | Teams and grounds added automatically outside the curated config, for review |
| `quarantine` | Matches set aside for a source error, with the rule and the detail |

## Player Lab (serving and players databases)

Built by `criciq_pipelines.players` during export. Super-over innings are excluded throughout.
**Par** columns hold what an average player of the same competition would have produced from the
same balls: the sum, over the player's balls, of the league rate for that ball's season and phase.
Summed over all players they equal the league's actual totals. The serving database holds the IPL's;
the [players database](#players-database-playersduckdb) holds every competition's (the first
ten tables below).

| Table | Grain | Notes |
|---|---|---|
| `league_phase_rates` | season × phase | Per-ball rates: runs, dismissals, boundaries and dots for batters; runs conceded, wickets, boundaries and dots for bowlers |
| `player_batting_innings` | player × innings | Runs, balls (excluding wides), 4s, 6s, dots, dismissal, position (order of arrival), season, venue, team, opposition, result, playoff flag, par columns |
| `player_bowling_innings` | player × innings | Legal balls, runs conceded (bat + wides + no-balls), wickets credited, maidens, dots, boundaries, wides, no-balls, context and par columns |
| `player_batting_cells` | player × season × phase × bowler type | Ball-level totals for phase and pace/spin splits; a non-striker run out counts in the cell of that ball |
| `player_bowling_cells` | player × season × phase × batter hand | Ball-level totals for phase and handedness splits |
| `player_batting_phases` | player × innings × phase | Balls, runs, dismissals and par in each phase of each innings: the units CricIQ Ratings are fitted on |
| `player_bowling_phases` | player × innings × phase | Legal balls, runs conceded, wickets and par in each phase of each innings |
| `player_fielding` | player × match | Catches (incl. caught and bowled), stumpings, run-out involvements; substitutes not credited |
| `player_seasons` | player × season × franchise | Appearances (playing XI and substitutes) |
| `player_index` | player | Directory: bio, career span, latest team, derived role (`batter`, `bowler`, `all_rounder` from balls per match), `is_keeper` (2+ stumpings), accent-free `search_key` |
| `matchup_cells` | batter × bowler × season × phase | Balls faced, runs, observed outcome counts `n_*` and the ball model's expected counts `e_*` (dot, one, two, three, four, six, out), written by `criciq-ml score` |
| `ball_model_terms` | term | The ball-outcome model's additive coefficients per outcome (intercept, situation levels, era, `batter=<id>`, `bowler=<id>`) |
| `player_wpa` | player × innings × role | Win probability added, written by `criciq-ml score`: each ball's change in the batting side's win probability goes to the batter and, negated, to the bowler |

CricIQ Ratings and similar players have no tables of their own: they are aggregates over the
tables above for the requested seasons (definitions in [metrics.md](metrics.md)). Their fitted
constants (`k`, `sigma2` and the stability label per component) are stored in `models` under the
name `ratings`, published by `criciq-ml score` from `models/ratings/<version>/manifest.json`.

## Players database (`players.duckdb`)

`data/exports/players.duckdb` (`criciq_pipelines.player_db`, ADR-0009): the Player Lab tables for
every T20 competition (the IPL, BBL, PSL, CPL, SA20 and T20Is), for all T20 cricket together,
for ODIs (whose phases are overs 1-10, 11-40 and 41-50) and for Tests (the new ball, overs 1-20;
the middle overs, 21-80; the second new ball, 81 on).

In schema `main`, every Player Lab table above has a leading `competition_id`, and the innings tables
also carry `global_order` (a match's order across every competition); `player_index` has `scope_id`
instead (a competition, or `T20`). Shared tables:

| Table | Notes |
|---|---|
| `scopes` | One row per scope: `scope_id` (`IPL` ... `T20I`, `T20` for all of them, then `ODI` and `TEST`), `schema_name` (its schema and API path segment, e.g. `sa20`), `name`, `short_name`, `format`, `competition_ids`, `display_order` |
| `competitions`, `matches`, `innings`, `wickets`, `players`, `venues` | The full warehouse's rows for the included competitions (slim columns) |
| `seasons` | As in the warehouse, plus `label`: "2023/24" where seasons span the new year (the BBL), else the year |
| `franchises` | Each competition's teams in the v1 shape; teams without curated colours (most associate nations) get neutral grey `#7A7A7A` |
| `meta` | `data_version`, `pipeline_version`, `built_at`, `competitions` |

One schema per scope (`ipl`, `bbl`, `psl`, `cpl`, `sa20`, `t20i`, `t20`, `odi`, `test`) holds views with the serving
database's table names and columns, restricted to the scope, so the API's Player Lab queries run on
any of them through `search_path`. In `t20` the competitions' rows are put together, each with its
own par; `player_index` (role, career span, latest team) is computed over all of them, and the
innings views' `match_order` is the order across every competition.

`criciq-ml score` adds the model outputs (`criciq_ml.players_scoring`):

| Table | Notes |
|---|---|
| `main.player_wpa` | Win probability added per player, innings and role, with `competition_id`, credited as in the serving database, from the win probability model serving each competition; each scope has a `player_wpa` view |
| `<scope>.models` | The scope's rating constants (`name = 'ratings'`, `info.components`), fitted on that scope's own records by its model group (`criciq-ml train ratings --group <group>`) |

## Team Analytics (serving database only)

Built by `criciq_pipelines.teams` during export. For the IPL, `config/league_tables.yaml` adds the
abandoned and voided fixtures, and the export fails if a computed league table differs from the
official one for any season the data fully covers; the other competitions' tables are computed
from results alone (two points a win) and not checked. A league's ground is a side's home in a
season when the side played most of its league matches there (in the IPL, grounds in India only);
a national side is at home in its own country (`home_countries` in `config/teams/national.yaml`
where that is several). Definitions are in [metrics.md](metrics.md).

| Table | Grain | Notes |
|---|---|---|
| `team_matches` | franchise × match | Both sides of every match: `result` (`won`, `lost`, `no_result`; a super-over tie counts for its winner, with `tied`), `in_table` (league and not voided), `batted_first`, `won_toss`, totals for and against, net run rate credits `nrr_*` (empty for no results), margins, `balls_to_spare`, `is_close`, `venue_type` (`home`, `away`, `neutral`) and `form_won`/`form_decided` (results in the side's previous 14 matches) |
| `team_innings_phases` | innings × phase | Runs (including extras), legal balls, dismissals, fours, sixes and dots, with batting and bowling franchise |
| `team_season_records` | franchise × season | League table: played, won, lost, no result, `abandoned`, points, net run rate (and its four sums), `position`, number of teams, `finish` (`champion`, `runner_up`, `playoffs`, `league`) and `exit_stage` |

## Simulator (serving database only)

Built by `criciq_pipelines.simulation` during export; the simulator's tuned settings are a row in
`models` (name `simulator`), published by `criciq-ml score`.

| Table | Grain | Notes |
|---|---|---|
| `bowling_usage` | player × season × franchise × over number | Overs bowled at each over number (0-19); an over belongs to the bowler of most of its legal balls. Drives which bowler a simulated captain picks for each over |
| `sim_league_rates` | season × innings × phase | Legal balls, run outs, and counts of legal balls by the extras that came with them (`x0` to `x5`, 5 meaning 5 or more): wides and no-balls before the ball, byes and leg byes on it |

## Model outputs (serving database only)

Written by `criciq-ml score` with the committed models; the API never runs a model.

| Table | Grain | Notes |
|---|---|---|
| `wp_predictions` | match × innings × state (`seq_no`, 0 = before the first ball) | `wp_team_a` (win probability of the side batting first), `factors` (explanation in points), `leverage` (expected swing of the next ball relative to a typical ball; empty once the innings is over), `pressure` (percentile of leverage among every state, 0-100), `momentum` (batting side's change in win probability over the last 12 legal balls, points). See [metrics.md](metrics.md) |
| `score_projections` | first-innings state | Quantiles of the final total |
| `models` | model name | Version, training seasons and served settings as JSON `info`; the win probability row also stores the pressure scale (mean swing and percentiles) |

## Data updates

The ingest database `data/sync/ingest.duckdb` (written by `criciq-data sync` and `run`, ADR-0008):

| Table | Grain | Notes |
|---|---|---|
| `ingest_log` | match | `competition_id`, `match_date`, `sha256` of the match file in use, `status` (`active`, `quarantined`, `withdrawn`), `source` (the archive holding that version, under `data/raw/`), `detail` (why a match, or its latest correction, is quarantined), `first_seen`, `updated_at` |
| `sync_runs` | run | `kind` (`initial`, `sync`, `full`, `rebuild`), `feed`, `status` (`updated`, `up_to_date`, `failed`), `data_version`, counts checked, new, corrected, withdrawn and quarantined, `seconds`, `detail` (why a run failed) |
| `data_updates` | run × competition | What a run changed in each competition: `new_matches`, `corrected_matches`, `withdrawn_matches`, `quarantined_matches`, `kind`, `updated_at` |

The serving database carries `data_updates` for its competition (empty until the first load is
recorded); the API's `/meta` reports the latest non-initial update as `last_update`.

## `meta`
Key/value build metadata: `data_version`, `pipeline_version`, `built_at`, `competition_id`,
`player_attributes`, and `season_spans_new_year` (`true` where seasons are named "2023/24").

Every competition on the site (the T20 competitions, ODIs and Tests) has a serving database of
its own with these tables
(`serving.duckdb` for the IPL, `serving-<competition>.duckdb` for the others; ADR-0011).

The Test serving database (`serving-test.duckdb`, ADR-0014) differs where Tests do:

| Table | Test-only columns and tables |
|---|---|
| `matches` | `win_by_innings`, `days` (the dates the match was played on) |
| `innings` | `declared`, `forfeited`, `follow_on`, `penalty_runs` |
| `match_summaries` | `won_by_innings`; `team_a_innings` and `team_b_innings`, each side's innings in order (runs, wickets, overs, declared, follow-on, forfeited); results read "Match drawn" and "won by an innings and N runs" |
| `team_matches` | `result` can be `drawn` |
| `team_season_records` | `drawn`, counted in `played` |
| `wp_predictions` | `wp_draw` beside `wp_team_a` (the side batting first wins); no explanations, pressure or momentum |
| `innings_projections` | Quantiles of every innings' final total after every ball (`match_id`, `innings_no`, `seq_no`, `quantiles`); limited-overs databases have `score_projections` for the first innings |
| `chase_states` | Every fourth-innings state with the columns the win probability model reads: where the chase what-if starts |
| `models` | `win_probability.info` holds the model's terms per innings and `now` (each side's rating and the scoring era after the last Test) for the chase calculator |
| `player_wpa` | Expected result added: a win counts 1, a draw a half |
