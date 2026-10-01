# Data Dictionary

Tables in the CricIQ warehouse (`data/warehouse/criciq.duckdb`). The authoritative DDL, with every
constraint, is [`schema.sql`](../pipelines/src/criciq_pipelines/sql/schema.sql). Core entities are
format-agnostic; IPL-specific knowledge lives in `config/`.

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
| `venue_aliases.raw_name` → `venue_id` | Every raw Cricsheet venue string |

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

## Player Lab (serving database only)

Built by `criciq_pipelines.players` during export. Super-over innings are excluded throughout.
**Par** columns hold what an average IPL player would have produced from the same balls: the sum,
over the player's balls, of the league rate for that ball's season and phase. Summed over all
players they equal the league's actual totals.

| Table | Grain | Notes |
|---|---|---|
| `league_phase_rates` | season × phase | Per-ball rates: runs, dismissals, boundaries and dots for batters; runs conceded, wickets, boundaries and dots for bowlers |
| `player_batting_innings` | player × innings | Runs, balls (excluding wides), 4s, 6s, dots, dismissal, position (order of arrival), season, venue, team, opposition, result, playoff flag, par columns |
| `player_bowling_innings` | player × innings | Legal balls, runs conceded (bat + wides + no-balls), wickets credited, maidens, dots, boundaries, wides, no-balls, context and par columns |
| `player_batting_cells` | player × season × phase × bowler type | Ball-level totals for phase and pace/spin splits; a non-striker run out counts in the cell of that ball |
| `player_bowling_cells` | player × season × phase × batter hand | Ball-level totals for phase and handedness splits |
| `player_fielding` | player × match | Catches (incl. caught and bowled), stumpings, run-out involvements; substitutes not credited |
| `player_seasons` | player × season × franchise | Appearances (playing XI and substitutes) |
| `player_index` | player | Directory: bio, career span, latest team, derived role (`batter`, `bowler`, `all_rounder` from balls per match), `is_keeper` (2+ stumpings), accent-free `search_key` |
| `player_wpa` | player × innings × role | Win probability added, written by `criciq-ml score`: each ball's change in the batting side's win probability goes to the batter and, negated, to the bowler |

## `meta`
Key/value build metadata: `data_version`, `pipeline_version`, `built_at`, `competition_id`,
`player_attributes`.
