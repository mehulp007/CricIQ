"""Service metadata: data version, seasons, franchises and venues."""

from __future__ import annotations

from criciq_api import __version__
from criciq_api.db import Database
from criciq_api.schemas.meta import FranchiseInfo, Meta, SeasonInfo, VenueInfo


def get_meta(db: Database) -> Meta:
    seasons = db.rows(
        """
        SELECT s.year, count(m.match_id) AS matches, s.impact_player_rule
        FROM seasons s LEFT JOIN matches m USING (season_id)
        GROUP BY s.year, s.impact_player_rule ORDER BY s.year
        """
    )
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
    return Meta(
        api_version="v1",
        app_version=__version__,
        data_version=db.data_version,
        model_versions={r["name"]: r["version"] for r in models},
        seasons=[SeasonInfo(**r) for r in seasons],
        franchises=[FranchiseInfo(**r) for r in franchises],
        venues=[VenueInfo(**r) for r in venues],
    )
