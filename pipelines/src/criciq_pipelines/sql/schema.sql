-- CricIQ warehouse schema (DuckDB).
--
-- Core entities are format-agnostic (competition, season, match, innings,
-- delivery, player, venue). Constraints are enforced by DuckDB on load, so a
-- successful build already guarantees keys, references and value domains.
-- See docs/data-dictionary.md for column-level documentation.

CREATE TABLE meta (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR NOT NULL
);

CREATE TABLE competitions (
    competition_id VARCHAR PRIMARY KEY,
    name           VARCHAR NOT NULL,
    short_name     VARCHAR NOT NULL,
    format         VARCHAR NOT NULL,
    gender         VARCHAR NOT NULL,
    team_type      VARCHAR NOT NULL
);

CREATE TABLE seasons (
    season_id          VARCHAR PRIMARY KEY,
    competition_id     VARCHAR NOT NULL REFERENCES competitions (competition_id),
    year               INTEGER NOT NULL,
    cricsheet_label    VARCHAR NOT NULL,
    impact_player_rule BOOLEAN NOT NULL,
    UNIQUE (competition_id, year)
);

CREATE TABLE franchises (
    franchise_id    VARCHAR PRIMARY KEY,
    competition_id  VARCHAR NOT NULL REFERENCES competitions (competition_id),
    name            VARCHAR NOT NULL,
    primary_color   VARCHAR NOT NULL,
    secondary_color VARCHAR NOT NULL,
    first_season    INTEGER NOT NULL,
    last_season     INTEGER,
    is_active       BOOLEAN NOT NULL
);

CREATE TABLE team_seasons (
    team_season_id VARCHAR PRIMARY KEY,
    franchise_id   VARCHAR NOT NULL REFERENCES franchises (franchise_id),
    season_id      VARCHAR NOT NULL REFERENCES seasons (season_id),
    display_name   VARCHAR NOT NULL,
    UNIQUE (franchise_id, season_id)
);

CREATE TABLE venues (
    venue_id VARCHAR PRIMARY KEY,
    name     VARCHAR NOT NULL,
    city     VARCHAR NOT NULL,
    country  VARCHAR NOT NULL,
    notes    VARCHAR
);

CREATE TABLE venue_aliases (
    raw_name VARCHAR PRIMARY KEY,
    venue_id VARCHAR NOT NULL REFERENCES venues (venue_id)
);

CREATE TABLE players (
    player_id         VARCHAR PRIMARY KEY,
    name              VARCHAR NOT NULL,
    unique_name       VARCHAR NOT NULL,
    full_name         VARCHAR,
    date_of_birth     DATE,
    country           VARCHAR,
    batting_hand      VARCHAR CHECK (batting_hand IN ('right', 'left')),
    bowling_arm       VARCHAR CHECK (bowling_arm IN ('right', 'left')),
    bowling_type      VARCHAR CHECK (bowling_type IN ('pace', 'spin')),
    bowling_style     VARCHAR,
    attributes_source VARCHAR
);

CREATE TABLE player_identifiers (
    player_id VARCHAR NOT NULL REFERENCES players (player_id),
    source    VARCHAR NOT NULL,
    value     VARCHAR NOT NULL,
    PRIMARY KEY (player_id, source)
);

CREATE TABLE matches (
    match_id              BIGINT PRIMARY KEY,
    competition_id        VARCHAR NOT NULL REFERENCES competitions (competition_id),
    season_id             VARCHAR NOT NULL REFERENCES seasons (season_id),
    match_order           INTEGER NOT NULL UNIQUE,
    match_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    match_number          INTEGER,
    stage                 VARCHAR NOT NULL,
    is_playoff            BOOLEAN NOT NULL,
    venue_id              VARCHAR NOT NULL REFERENCES venues (venue_id),
    team1_id              VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    team2_id              VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    toss_winner_id        VARCHAR REFERENCES team_seasons (team_season_id),
    toss_decision         VARCHAR CHECK (toss_decision IN ('bat', 'field')),
    outcome_type          VARCHAR NOT NULL CHECK (outcome_type IN ('win', 'tie', 'no_result')),
    winner_id             VARCHAR REFERENCES team_seasons (team_season_id),
    win_by_runs           INTEGER,
    win_by_wickets        INTEGER,
    win_method            VARCHAR,
    decided_by_super_over BOOLEAN NOT NULL,
    scheduled_overs       INTEGER NOT NULL,
    balls_per_over        INTEGER NOT NULL,
    player_of_match_ids   VARCHAR[] NOT NULL,
    cricsheet_version     VARCHAR,
    CHECK (team1_id <> team2_id)
);

CREATE TABLE innings (
    match_id             BIGINT NOT NULL REFERENCES matches (match_id),
    innings_no           INTEGER NOT NULL,
    batting_team_id      VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    bowling_team_id      VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    is_super_over        BOOLEAN NOT NULL,
    target_runs          INTEGER,
    target_overs         DOUBLE,
    target_balls         INTEGER,
    runs                 INTEGER NOT NULL,
    wickets              INTEGER NOT NULL,
    legal_balls          INTEGER NOT NULL,
    extras               INTEGER NOT NULL,
    absent_hurt_ids      VARCHAR[] NOT NULL,
    miscounted_overs     VARCHAR,
    PRIMARY KEY (match_id, innings_no)
);

CREATE TABLE deliveries (
    match_id          BIGINT NOT NULL,
    innings_no        INTEGER NOT NULL,
    seq_no            INTEGER NOT NULL,
    over_no           INTEGER NOT NULL,
    ball_label        VARCHAR,
    legal_ball_no     INTEGER NOT NULL,
    is_legal          BOOLEAN NOT NULL,
    batting_team_id   VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    bowling_team_id   VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    batter_id         VARCHAR NOT NULL REFERENCES players (player_id),
    non_striker_id    VARCHAR NOT NULL REFERENCES players (player_id),
    bowler_id         VARCHAR NOT NULL REFERENCES players (player_id),
    runs_batter       INTEGER NOT NULL,
    runs_extras       INTEGER NOT NULL,
    runs_total        INTEGER NOT NULL,
    is_four           BOOLEAN NOT NULL,
    is_six            BOOLEAN NOT NULL,
    extras_wides      INTEGER NOT NULL,
    extras_noballs    INTEGER NOT NULL,
    extras_byes       INTEGER NOT NULL,
    extras_legbyes    INTEGER NOT NULL,
    extras_penalty    INTEGER NOT NULL,
    is_wicket         BOOLEAN NOT NULL,
    team_runs         INTEGER NOT NULL,
    team_wickets      INTEGER NOT NULL,
    has_review        BOOLEAN NOT NULL,
    PRIMARY KEY (match_id, innings_no, seq_no),
    FOREIGN KEY (match_id, innings_no) REFERENCES innings (match_id, innings_no),
    CHECK (runs_total = runs_batter + runs_extras)
);

CREATE TABLE wickets (
    match_id         BIGINT NOT NULL,
    innings_no       INTEGER NOT NULL,
    seq_no           INTEGER NOT NULL,
    wicket_no        INTEGER NOT NULL,
    player_out_id    VARCHAR NOT NULL REFERENCES players (player_id),
    kind             VARCHAR NOT NULL,
    is_dismissal     BOOLEAN NOT NULL,
    bowler_credited  BOOLEAN NOT NULL,
    bowler_id        VARCHAR NOT NULL REFERENCES players (player_id),
    fielder_ids      VARCHAR[] NOT NULL,
    fielder_is_substitute BOOLEAN[] NOT NULL,
    PRIMARY KEY (match_id, innings_no, seq_no, wicket_no),
    FOREIGN KEY (match_id, innings_no, seq_no) REFERENCES deliveries (match_id, innings_no, seq_no)
);

CREATE TABLE match_players (
    match_id        BIGINT NOT NULL REFERENCES matches (match_id),
    team_season_id  VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    player_id       VARCHAR NOT NULL REFERENCES players (player_id),
    list_position   INTEGER NOT NULL,
    selection       VARCHAR NOT NULL
        CHECK (selection IN ('playing_xi', 'impact_substitute', 'concussion_substitute')),
    substituted_out BOOLEAN NOT NULL,
    PRIMARY KEY (match_id, player_id)
);

CREATE TABLE substitutions (
    match_id       BIGINT NOT NULL,
    innings_no     INTEGER NOT NULL,
    seq_no         INTEGER NOT NULL,
    sub_no         INTEGER NOT NULL,
    kind           VARCHAR NOT NULL CHECK (kind IN ('match', 'role')),
    reason         VARCHAR,
    team_season_id VARCHAR NOT NULL REFERENCES team_seasons (team_season_id),
    player_in_id   VARCHAR REFERENCES players (player_id),
    player_out_id  VARCHAR REFERENCES players (player_id),
    role           VARCHAR,
    PRIMARY KEY (match_id, innings_no, seq_no, sub_no),
    FOREIGN KEY (match_id, innings_no, seq_no) REFERENCES deliveries (match_id, innings_no, seq_no)
);
