from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from criciq_pipelines.raw import RawSnapshot
from criciq_pipelines.warehouse import BuildInputs, WarehouseBuildError, build_warehouse


@pytest.fixture
def con(fixture_warehouse: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(fixture_warehouse), read_only=True)
    yield connection
    connection.close()


def scalar(con: duckdb.DuckDBPyConnection, sql: str) -> object:
    row = con.execute(sql).fetchone()
    assert row is not None
    return row[0]


def test_all_fixture_matches_load(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT count(*) FROM matches") == 14
    assert scalar(con, "SELECT value FROM meta WHERE key = 'data_version'")


def test_team_names_map_to_franchises_per_season(con: duckdb.DuckDBPyConnection) -> None:
    franchise_ids = {
        row[0]
        for row in con.execute(
            "SELECT franchise_id FROM team_seasons WHERE display_name LIKE 'Delhi%'"
        ).fetchall()
    }
    assert franchise_ids == {"DC"}
    teams = con.execute("SELECT team1_id, team2_id FROM matches WHERE match_id = 335982").fetchone()
    assert teams is not None
    assert set(teams) == {"KKR-2008", "RCB-2008"}


def test_venue_is_canonical(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT venue_id FROM matches WHERE match_id = 335982") == "chinnaswamy"


def test_match_order_is_chronological(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        "SELECT match_order, match_date FROM matches ORDER BY match_order"
    ).fetchall()
    assert [r[0] for r in rows] == list(range(1, len(rows) + 1))
    assert [r[1] for r in rows] == sorted(r[1] for r in rows)


def test_running_score_and_boundaries(con: duckdb.DuckDBPyConnection) -> None:
    last = con.execute(
        """SELECT team_runs, team_wickets FROM deliveries
           WHERE match_id = 335982 AND innings_no = 2 ORDER BY seq_no DESC LIMIT 1"""
    ).fetchone()
    assert last == (82, 10)
    assert scalar(con, "SELECT count(*) FROM deliveries WHERE is_four AND runs_batter <> 4") == 0


def test_revised_target_converts_fractional_overs(con: duckdb.DuckDBPyConnection) -> None:
    row = con.execute(
        "SELECT target_overs, target_balls FROM innings WHERE match_id = 392186 AND innings_no = 2"
    ).fetchone()
    assert row == (9.2, 56)


def test_retirements(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT bool_and(is_dismissal) FROM wickets WHERE kind = 'retired out'")
    hurt = scalar(con, "SELECT bool_or(is_dismissal) FROM wickets WHERE kind = 'retired hurt'")
    assert hurt in (False, None)


def test_bowler_credit(con: duckdb.DuckDBPyConnection) -> None:
    credited = dict(
        con.execute("SELECT kind, bool_and(bowler_credited) FROM wickets GROUP BY 1").fetchall()
    )
    assert credited["caught"] is True
    assert credited["run out"] is False


def test_substitutes_are_flagged(con: duckdb.DuckDBPyConnection) -> None:
    impact = con.execute(
        """SELECT count(*) FILTER (WHERE selection = 'impact_substitute'),
                  count(*) FILTER (WHERE substituted_out)
           FROM match_players WHERE match_id = 1473511"""
    ).fetchone()
    assert impact == (2, 2)
    concussion = scalar(
        con, "SELECT count(*) FROM match_players WHERE selection = 'concussion_substitute'"
    )
    assert isinstance(concussion, int)
    assert concussion >= 1


def test_player_attributes_are_joined(con: duckdb.DuckDBPyConnection) -> None:
    row = con.execute(
        "SELECT full_name, batting_hand FROM players WHERE name = 'BB McCullum'"
    ).fetchone()
    assert row == ("Brendon McCullum", "right")


def test_unmapped_venue_fails_the_build(
    fixture_snapshot: RawSnapshot, fixture_interim: Path, tmp_path: Path
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    source = Path(__file__).resolve().parents[2] / "config"
    for name in ("competitions.yaml", "franchises.yaml", "golden_matches.yaml"):
        (config / name).write_text((source / name).read_text("utf-8"), "utf-8")
    (config / "venues.yaml").write_text(
        "venues:\n  - {id: x, name: X, city: Y, country: Z, aliases: [Nowhere]}\n", "utf-8"
    )
    target = tmp_path / "w.duckdb"
    with pytest.raises(WarehouseBuildError, match="unmapped venues"):
        build_warehouse(
            BuildInputs(fixture_interim, fixture_snapshot.people, "test", None, config), target
        )
    assert not target.exists()  # a failed build never replaces the warehouse
