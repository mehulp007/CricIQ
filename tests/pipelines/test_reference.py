import pytest

from criciq_pipelines.reference import (
    load_competitions,
    load_franchises,
    load_golden_matches,
    load_venues,
)


def test_renamed_franchises_resolve_by_season() -> None:
    franchises = load_franchises()
    assert franchises.resolve("Delhi Daredevils", 2012).id == "DC"
    assert franchises.resolve("Delhi Capitals", 2024).id == "DC"
    assert franchises.resolve("Kings XI Punjab", 2019).id == "PBKS"
    assert franchises.resolve("Royal Challengers Bengaluru", 2025).id == "RCB"
    assert franchises.resolve("Rising Pune Supergiants", 2016).id == "RPS"
    assert franchises.resolve("Rising Pune Supergiant", 2017).id == "RPS"


def test_deccan_chargers_are_not_sunrisers() -> None:
    franchises = load_franchises()
    assert franchises.resolve("Deccan Chargers", 2009).id == "DCH"
    assert franchises.resolve("Sunrisers Hyderabad", 2016).id == "SRH"


@pytest.mark.parametrize(
    ("name", "season"),
    [
        ("Delhi Capitals", 2012),
        ("Punjab Kings", 2019),
        ("Gujarat Titans", 2017),
        ("Unknown XI", 2020),
    ],
)
def test_names_outside_their_seasons_are_rejected(name: str, season: int) -> None:
    with pytest.raises(LookupError, match=r"franchises\.yaml"):
        load_franchises().resolve(name, season)


def test_venue_renames_share_one_ground() -> None:
    aliases = load_venues().alias_map()
    assert aliases["Feroz Shah Kotla"] == aliases["Arun Jaitley Stadium, Delhi"] == "arun-jaitley"
    assert aliases["M.Chinnaswamy Stadium"] == aliases["M Chinnaswamy Stadium, Bengaluru"]
    # A rebuilt stadium and a different ground in the same region stay separate.
    assert aliases["Sardar Patel Stadium, Motera"] != aliases["Narendra Modi Stadium, Ahmedabad"]
    assert (
        aliases["Punjab Cricket Association Stadium, Mohali"]
        != aliases["Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur"]
    )


def test_competition_and_golden_config_load() -> None:
    ipl = load_competitions().get("IPL")
    assert ipl.rules.impact_player_from == 2023
    golden = load_golden_matches()
    assert {g.match_id for g in golden.matches} >= {335982, 1181768, 1370353}
