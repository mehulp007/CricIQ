"""Extract: Cricsheet JSON (format 1.x) -> flat, typed Parquet tables.

This step only *flattens* and resolves names to Cricsheet person ids through
each match's own registry. It does not map teams or venues; that is the
warehouse step's job, driven by the reference config.
"""

from __future__ import annotations

import datetime as dt
import json
import zipfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from criciq_core.cricket import is_legal_delivery

Row = dict[str, Any]

SCHEMAS: dict[str, pa.Schema] = {
    "matches": pa.schema(
        [
            ("match_id", pa.int64()),
            ("cricsheet_version", pa.string()),
            ("event_name", pa.string()),
            ("season_label", pa.string()),
            ("match_date", pa.date32()),
            ("end_date", pa.date32()),
            ("match_number", pa.int32()),
            ("stage", pa.string()),
            ("gender", pa.string()),
            ("match_type", pa.string()),
            ("team_type", pa.string()),
            ("scheduled_overs", pa.int32()),
            ("balls_per_over", pa.int32()),
            ("venue_raw", pa.string()),
            ("city_raw", pa.string()),
            ("team1", pa.string()),
            ("team2", pa.string()),
            ("toss_winner", pa.string()),
            ("toss_decision", pa.string()),
            ("outcome_winner", pa.string()),
            ("outcome_result", pa.string()),
            ("outcome_eliminator", pa.string()),
            ("outcome_by_runs", pa.int32()),
            ("outcome_by_wickets", pa.int32()),
            ("outcome_method", pa.string()),
            ("player_of_match_ids", pa.list_(pa.string())),
        ]
    ),
    "innings": pa.schema(
        [
            ("match_id", pa.int64()),
            ("innings_no", pa.int32()),
            ("team", pa.string()),
            ("is_super_over", pa.bool_()),
            ("target_runs", pa.int32()),
            ("target_overs", pa.float64()),
            ("absent_hurt_ids", pa.list_(pa.string())),
            ("miscounted_overs_json", pa.string()),
        ]
    ),
    "deliveries": pa.schema(
        [
            ("match_id", pa.int64()),
            ("innings_no", pa.int32()),
            ("seq_no", pa.int32()),
            ("over_no", pa.int32()),
            ("ball_label", pa.string()),
            ("legal_ball_no", pa.int32()),
            ("is_legal", pa.bool_()),
            ("batter_id", pa.string()),
            ("non_striker_id", pa.string()),
            ("bowler_id", pa.string()),
            ("runs_batter", pa.int32()),
            ("runs_extras", pa.int32()),
            ("runs_total", pa.int32()),
            ("non_boundary", pa.bool_()),
            ("extras_wides", pa.int32()),
            ("extras_noballs", pa.int32()),
            ("extras_byes", pa.int32()),
            ("extras_legbyes", pa.int32()),
            ("extras_penalty", pa.int32()),
            ("has_review", pa.bool_()),
        ]
    ),
    "wickets": pa.schema(
        [
            ("match_id", pa.int64()),
            ("innings_no", pa.int32()),
            ("seq_no", pa.int32()),
            ("wicket_no", pa.int32()),
            ("player_out_id", pa.string()),
            ("kind", pa.string()),
            ("fielder_ids", pa.list_(pa.string())),
            ("fielder_is_substitute", pa.list_(pa.bool_())),
        ]
    ),
    "replacements": pa.schema(
        [
            ("match_id", pa.int64()),
            ("innings_no", pa.int32()),
            ("seq_no", pa.int32()),
            ("kind", pa.string()),
            ("team", pa.string()),
            ("player_in_id", pa.string()),
            ("player_out_id", pa.string()),
            ("reason", pa.string()),
            ("role", pa.string()),
        ]
    ),
    "match_players": pa.schema(
        [
            ("match_id", pa.int64()),
            ("team", pa.string()),
            ("list_position", pa.int32()),
            ("player_id", pa.string()),
        ]
    ),
    "registry": pa.schema(
        [
            ("match_id", pa.int64()),
            ("name", pa.string()),
            ("person_id", pa.string()),
        ]
    ),
}


class ExtractError(ValueError):
    """Raised when a match file cannot be flattened safely."""


def parse_match(match_id: int, doc: dict[str, Any]) -> dict[str, list[Row]]:
    """Flatten one Cricsheet match document into rows for each interim table."""
    info = doc["info"]
    registry: dict[str, str] = info.get("registry", {}).get("people", {})

    def pid(name: str | None) -> str | None:
        if name is None:
            return None
        try:
            return registry[name]
        except KeyError:
            raise ExtractError(f"match {match_id}: {name!r} missing from registry") from None

    outcome = info.get("outcome", {})
    by = outcome.get("by", {})
    event = info.get("event", {})
    teams = info["teams"]
    if len(teams) != 2:
        raise ExtractError(f"match {match_id}: expected 2 teams, got {teams}")

    rows: dict[str, list[Row]] = {name: [] for name in SCHEMAS}
    rows["matches"].append(
        {
            "match_id": match_id,
            "cricsheet_version": doc.get("meta", {}).get("data_version"),
            "event_name": event.get("name"),
            "season_label": str(info.get("season")),
            "match_date": dt.date.fromisoformat(info["dates"][0]),
            "end_date": dt.date.fromisoformat(info["dates"][-1]),
            "match_number": event.get("match_number"),
            "stage": event.get("stage"),
            "gender": info.get("gender"),
            "match_type": info.get("match_type"),
            "team_type": info.get("team_type"),
            "scheduled_overs": info.get("overs"),
            "balls_per_over": info.get("balls_per_over", 6),
            "venue_raw": info.get("venue"),
            "city_raw": info.get("city"),
            "team1": teams[0],
            "team2": teams[1],
            "toss_winner": info.get("toss", {}).get("winner"),
            "toss_decision": info.get("toss", {}).get("decision"),
            "outcome_winner": outcome.get("winner"),
            "outcome_result": outcome.get("result"),
            "outcome_eliminator": outcome.get("eliminator"),
            "outcome_by_runs": by.get("runs"),
            "outcome_by_wickets": by.get("wickets"),
            "outcome_method": outcome.get("method"),
            "player_of_match_ids": [pid(p) for p in info.get("player_of_match", [])],
        }
    )

    for team, players in info.get("players", {}).items():
        for position, name in enumerate(players, start=1):
            rows["match_players"].append(
                {
                    "match_id": match_id,
                    "team": team,
                    "list_position": position,
                    "player_id": pid(name),
                }
            )
    for name, person_id in sorted(registry.items()):
        rows["registry"].append({"match_id": match_id, "name": name, "person_id": person_id})

    for innings_no, innings in enumerate(doc.get("innings", []), start=1):
        target = innings.get("target", {})
        rows["innings"].append(
            {
                "match_id": match_id,
                "innings_no": innings_no,
                "team": innings["team"],
                "is_super_over": bool(innings.get("super_over", False)),
                "target_runs": target.get("runs"),
                "target_overs": target.get("overs"),
                "absent_hurt_ids": [pid(p) for p in innings.get("absent_hurt", [])],
                "miscounted_overs_json": (
                    json.dumps(innings["miscounted_overs"], sort_keys=True)
                    if "miscounted_overs" in innings
                    else None
                ),
            }
        )
        _parse_deliveries(match_id, innings_no, innings, pid, rows)
    return rows


def _parse_deliveries(
    match_id: int,
    innings_no: int,
    innings: dict[str, Any],
    pid: Any,
    rows: dict[str, list[Row]],
) -> None:
    seq_no = 0
    legal_balls = 0
    for over in innings.get("overs", []):
        for delivery in over["deliveries"]:
            seq_no += 1
            extras = delivery.get("extras", {})
            wides, noballs = extras.get("wides", 0), extras.get("noballs", 0)
            legal = is_legal_delivery(wides, noballs)
            legal_balls += legal
            runs = delivery["runs"]
            if runs["total"] != runs["batter"] + runs["extras"]:
                raise ExtractError(f"match {match_id} inn {innings_no} seq {seq_no}: runs mismatch")
            rows["deliveries"].append(
                {
                    "match_id": match_id,
                    "innings_no": innings_no,
                    "seq_no": seq_no,
                    "over_no": over["over"],
                    "ball_label": delivery.get("actual_delivery"),
                    "legal_ball_no": legal_balls,
                    "is_legal": legal,
                    "batter_id": pid(delivery["batter"]),
                    "non_striker_id": pid(delivery["non_striker"]),
                    "bowler_id": pid(delivery["bowler"]),
                    "runs_batter": runs["batter"],
                    "runs_extras": runs["extras"],
                    "runs_total": runs["total"],
                    "non_boundary": bool(runs.get("non_boundary", False)),
                    "extras_wides": wides,
                    "extras_noballs": noballs,
                    "extras_byes": extras.get("byes", 0),
                    "extras_legbyes": extras.get("legbyes", 0),
                    "extras_penalty": extras.get("penalty", 0),
                    "has_review": "review" in delivery,
                }
            )
            for wicket_no, wicket in enumerate(delivery.get("wickets", []), start=1):
                fielders = wicket.get("fielders", [])
                rows["wickets"].append(
                    {
                        "match_id": match_id,
                        "innings_no": innings_no,
                        "seq_no": seq_no,
                        "wicket_no": wicket_no,
                        "player_out_id": pid(wicket["player_out"]),
                        "kind": wicket["kind"],
                        "fielder_ids": [pid(f["name"]) for f in fielders if "name" in f],
                        "fielder_is_substitute": [
                            bool(f.get("substitute", False)) for f in fielders if "name" in f
                        ],
                    }
                )
            for kind, entries in delivery.get("replacements", {}).items():
                for entry in entries:
                    rows["replacements"].append(
                        {
                            "match_id": match_id,
                            "innings_no": innings_no,
                            "seq_no": seq_no,
                            "kind": kind,
                            "team": entry.get("team"),
                            "player_in_id": pid(entry.get("in")),
                            "player_out_id": pid(entry.get("out")),
                            "reason": entry.get("reason"),
                            "role": entry.get("role"),
                        }
                    )


def iter_archive(archive: Path) -> list[tuple[int, dict[str, Any]]]:
    """All matches in a Cricsheet zip as (match_id, document), sorted by id."""
    matches: list[tuple[int, dict[str, Any]]] = []
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if name.endswith(".json"):
                matches.append((int(Path(name).stem), json.loads(zf.read(name))))
    return sorted(matches, key=lambda m: m[0])


def extract_archive(archive: Path, out_dir: Path) -> dict[str, int]:
    """Flatten every match in the archive and write one Parquet file per table."""
    tables: dict[str, list[Row]] = {name: [] for name in SCHEMAS}
    for match_id, doc in iter_archive(archive):
        for name, rows in parse_match(match_id, doc).items():
            tables[name].extend(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name, rows in tables.items():
        table = pa.Table.from_pylist(rows, schema=SCHEMAS[name])
        pq.write_table(table, out_dir / f"{name}.parquet", compression="zstd")
        counts[name] = table.num_rows
    return counts
