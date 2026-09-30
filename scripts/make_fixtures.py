"""Regenerate the Cricsheet test fixtures from the latest raw snapshot.

Usage:  uv run python scripts/make_fixtures.py

Writes a small, edge-case-rich subset of real matches (minified JSON) and the
matching rows of Cricsheet's people register to tests/fixtures/cricsheet/.
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
}

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "cricsheet"


def main() -> None:
    snapshot = latest_snapshot()
    matches_dir = OUT / "matches"
    matches_dir.mkdir(parents=True, exist_ok=True)
    for stale in matches_dir.glob("*.json"):
        stale.unlink()

    people_ids: set[str] = set()
    with zipfile.ZipFile(snapshot.archive) as zf:
        for match_id in sorted(FIXTURE_MATCHES):
            doc = json.loads(zf.read(f"{match_id}.json"))
            people_ids.update(doc["info"]["registry"]["people"].values())
            (matches_dir / f"{match_id}.json").write_text(
                json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n", "utf-8"
            )

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
