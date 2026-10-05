-- CricIQ warehouse schema (DuckDB): every competition, every format.
--
-- Core entities are format-agnostic (competition, season, team, match, innings,
-- delivery, player, venue). Constraints are enforced by DuckDB on load, so a
-- successful build already guarantees keys, references and value domains.
-- Per-competition copies in the v1 shape are built from it by
-- criciq_pipelines.scope. See docs/data-dictionary.md for column-level docs.

CREATE TABLE meta (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR NOT NULL
);

CREATE TABLE competitions (
    competition_id VARCHAR PRIMARY KEY,
    name           VARCHAR NOT NULL,
    short_name     VARCHAR NOT NULL,
    format         VARCHAR NOT NULL CHECK (format IN ('T20', 'ODI', 'Test')),
    gender         VARCHAR NOT NULL,
    team_type      VARCHAR NOT NULL CHECK (team_type IN ('club', 'national')),
    switcher       BOOLEAN NOT NULL
);

CREATE TABLE seasons (
    season_id          VARCHAR PRIMARY KEY,
    competition_id     VARCHAR NOT NULL REFERENCES competitions (competition_id),
    year               INTEGER NOT NULL,
    cricsheet_label    VARCHAR NOT NULL,
    impact_player_rule BOOLEAN NOT NULL,
    start_date         DATE NOT NULL,
    end_date           DATE NOT NULL,
    UNIQUE (competition_id, year)
);

-- A team is one identity across seasons (and, for national sides, formats).
CREATE TABLE teams (
    team_id         VARCHAR PRIMARY KEY,
    name            VARCHAR NOT NULL,
    team_type       VARCHAR NOT NULL CHECK (team_type IN ('club', 'national')),
    primary_color   VARCHAR,
    secondary_color VARCHAR,
    is_curated      BOOLEAN NOT NULL
);

CREATE TABLE competition_teams (
    competition_id VARCHAR NOT NULL REFERENCES competitions (competition_id),
    team_id        VARCHAR NOT NULL REFERENCES teams (team_id),
    first_season   INTEGER NOT NULL,
    last_season    INTEGER,
    is_active      BOOLEAN NOT NULL,
    PRIMARY KEY (competition_id, team_id)
);

CREATE TABLE team_seasons (
    team_season_id VARCHAR PRIMARY KEY,
    team_id        VARCHAR NOT NULL REFERENCES teams (team_id),
    season_id      VARCHAR NOT NULL REFERENCES seasons (season_id),
    display_name   VARCHAR NOT NULL,
    UNIQUE (team_id, season_id)
);

CREATE TABLE venues (
    venue_id   VARCHAR PRIMARY KEY,
    name       VARCHAR NOT NULL,
    city       VARCHAR,
    country    VARCHAR,
    notes      VARCHAR,
    is_curated BOOLEAN NOT NULL
);

CREATE TABLE venue_aliases (
    raw_name   VARCHAR PRIMARY KEY,
    venue_id   VARCHAR NOT NULL REFERENCES venues (venue_id),
    is_curated BOOLEAN NOT NULL
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
    -- Chronological order within the competition, and across every competition.
    match_order           INTEGER NOT NULL,
    global_order          INTEGER NOT NULL UNIQUE,
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
    outcome_type          VARCHAR NOT NULL
        CHECK (outcome_type IN ('win', 'tie', 'draw', 'no_result')),
    winner_id             VARCHAR REFERENCES team_seasons (team_season_id),
    win_by_runs           INTEGER,
    win_by_wickets        INTEGER,
    win_by_innings        INTEGER,
    win_method            VARCHAR,
    decided_by_super_over BOOLEAN NOT NULL,
    decided_by_bowl_out   BOOLEAN NOT NULL,
    -- NULL for Tests, which have no over limit.
    scheduled_overs       INTEGER,
    balls_per_over        INTEGER NOT NULL,
    days                  INTEGER NOT NULL,
    player_of_match_ids   VARCHAR[] NOT NULL,
    cricsheet_version     VARCHAR,
    event_name            VARCHAR,
    match_type_number     INTEGER,
    has_supersubs         BOOLEAN NOT NULL,
    UNIQUE (competition_id, match_order),
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
    -- Includes penalty runs awarded before or after the innings.
    runs                 INTEGER NOT NULL,
    wickets              INTEGER NOT NULL,
    legal_balls          INTEGER NOT NULL,
    extras               INTEGER NOT NULL,
    absent_hurt_ids      VARCHAR[] NOT NULL,
    miscounted_overs     VARCHAR,
    declared             BOOLEAN NOT NULL,
    forfeited            BOOLEAN NOT NULL,
    -- The batting side followed on (Tests): it bats twice in a row.
    follow_on            BOOLEAN NOT NULL,
    penalty_runs         INTEGER NOT NULL,
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
