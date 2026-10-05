"""Regenerate the Cricsheet test fixtures from the latest raw snapshot.

Usage:  uv run python scripts/make_fixtures.py

Writes a small, edge-case-rich subset of real matches from every competition
(minified JSON) and the matching rows of Cricsheet's people register to
tests/fixtures/cricsheet/. The IPL matches build the v1-shaped IPL warehouse
the export and the models are tested on; the others exercise other leagues,
national sides and Test cricket in the multi-competition warehouse.
"""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

from criciq_pipelines.raw import latest_snapshot

# match_id -> why it is in the fixture set
FIXTURE_MATCHES: dict[int, str] = {
    335982: "2008 opener (golden)",
    981019: "2016 final (golden)",
    1181768: "2019 final, one-run margin (golden)",
    1370353: "2023 final, DLS chase with revised target (golden)",
    1473511: "2025 final, Impact Player era (golden)",
    1082625: "2017 tie decided by a super over (golden)",
    1216517: "tie that needed two super overs",
    1359519: "no result after one innings",
    392186: "D/L chase with fractional target overs (9.2) won 'by runs'",
    419155: "umpire-miscounted 7-ball over",
    335988: "penalty runs",
    392202: "mid-over bowler replacement (injury) and absent-hurt batter",
    1370352: "concussion substitute",
    1304066: "batter retired out",
    # Other T20 leagues
    1386137: "BBL 2023/24 final: a season spanning two calendar years (golden)",
    1386128: "BBL match with penalty runs awarded outside the deliveries",
    1211672: "PSL 2020 playoff played in November 2020, labelled 2020/21 by Cricsheet",
    1247044: "PSL 2021 after the break, labelled 2021",
    635216: "CPL 2013: Trinidad & Tobago Red Steel, later Trinbago Knight Riders",
    1343973: "SA20 2023 final (golden)",
    # Men's T20 internationals
    951373: "2016 World T20 final (golden)",
    287862: "2007 World T20: tie settled by a bowl-out",
    1229824: "source error: one register id on both sides (quarantined)",
    1481295: "a side of ten players (a note, not an error)",
    # Men's ODIs
    1144530: "2019 World Cup final: tie, super-over tie, boundary count (golden)",
    224227: "2005 supersub rule (twelve players) and a D/L result",
    1420222: "penalty runs in an ODI",
    # Men's Tests
    215010: "2005 Edgbaston: win by runs over four innings (golden)",
    1223869: "2020 Adelaide: 36/9, win by wickets (golden)",
    1223871: "2021 Sydney: declaration and a draw (golden)",
    1122310: "follow-on and an innings victory",
}

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "cricsheet"


def main() -> None:
    snapshot = latest_snapshot()
    matches_dir = OUT / "matches"
    matches_dir.mkdir(parents=True, exist_ok=True)
    for stale in matches_dir.glob("*.json"):
        stale.unlink()

    people_ids: set[str] = set()
    wanted = {f"{match_id}.json" for match_id in FIXTURE_MATCHES}
    for archive in snapshot.archives:
        with zipfile.ZipFile(archive) as zf:
            for name in sorted(wanted & set(zf.namelist())):
                doc = json.loads(zf.read(name))
                people_ids.update(doc["info"]["registry"]["people"].values())
                (matches_dir / name).write_text(
                    json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n",
                    "utf-8",
                    newline="\n",
                )
                wanted.discard(name)
    if wanted:
        raise SystemExit(f"not in the latest snapshot: {sorted(wanted)}")

    with snapshot.people.open(encoding="utf-8", newline="") as src:
        reader = csv.DictReader(src)
        rows = [row for row in reader if row["identifier"] in people_ids]
        fieldnames = reader.fieldnames or []
    with (OUT / "people.csv").open("w", encoding="utf-8", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["identifier"]))

    print(f"wrote {len(FIXTURE_MATCHES)} matches and {len(rows)} people to {OUT}")


if __name__ == "__main__":
    main()
