"""Service metadata: the competition, data version, seasons, teams and venues."""

from __future__ import annotations

from criciq_api import __version__
from criciq_api.db import Database
from criciq_api.schemas.meta import (
    CompetitionInfo,
    DataUpdate,
    Features,
    FranchiseInfo,
    Meta,
    SeasonInfo,
    VenueInfo,
)


def get_meta(db: Database) -> Meta:
    seasons = db.rows(
        """
        SELECT s.year, CASE WHEN ? THEN s.cricsheet_label ELSE s.year::VARCHAR END AS label,
               count(m.match_id) AS matches, s.impact_player_rule
        FROM seasons s LEFT JOIN matches m USING (season_id)
        GROUP BY ALL ORDER BY s.year
        """,
        [db.season_spans_new_year],
    )
    competition = db.row(
        "SELECT competition_id, name, short_name, format, team_type FROM competitions LIMIT 1"
    )
    assert competition is not None
    franchises = db.rows(
        """
        SELECT franchise_id, name, primary_color, secondary_color, first_season, last_season,
               is_active
        FROM franchises ORDER BY NOT is_active, name
        """
    )
    venues = db.rows(
        """
        SELECT v.venue_id, v.name, v.city, v.country, count(m.match_id) AS matches
        FROM venues v LEFT JOIN matches m USING (venue_id)
        GROUP BY ALL ORDER BY matches DESC, v.name
        """
    )
    models = (
        db.rows("SELECT name, version FROM models ORDER BY name") if db.has_table("models") else []
    )
    # The first full load is not an update: everything in it is "new".
    update = (
        db.row(
            """
            SELECT updated_at, sum(new_matches) AS new_matches,
                   sum(corrected_matches) AS corrected_matches,
                   sum(withdrawn_matches) AS withdrawn_matches
            FROM data_updates
            WHERE kind <> 'initial'
              AND new_matches + corrected_matches + withdrawn_matches > 0
            GROUP BY run_id, updated_at ORDER BY run_id DESC LIMIT 1
            """
        )
        if db.has_table("data_updates")
        else None
    )
    served = {r["name"] for r in models}
    return Meta(
        api_version="v2",
        app_version=__version__,
        competition=CompetitionInfo(
            id=competition["competition_id"].lower(),
            name=competition["name"],
            short_name=competition["short_name"],
            format=competition["format"],
            team_type=competition["team_type"],
        ),
        features=Features(
            win_probability="win_probability" in served,
            score_projection="score_projection" in served,
            ball_model="ball_outcome" in served,
            simulator="simulator" in served,
        ),
        data_version=db.data_version,
        model_versions={r["name"]: r["version"] for r in models},
        latest_match_date=db.scalar("SELECT max(match_date) FROM matches"),
        last_update=DataUpdate(**update) if update else None,
        seasons=[SeasonInfo(**r) for r in seasons],
        franchises=[FranchiseInfo(**r) for r in franchises],
        venues=[VenueInfo(**r) for r in venues],
    )
