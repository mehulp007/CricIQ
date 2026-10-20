"""scripts/data_snapshot.py: packing the served databases and installing them again."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import duckdb
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "data_snapshot.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("data_snapshot", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snapshot = load()


def database(path: Path, version: str = "2026-10-14.abc", rows: int = 3) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE meta (key VARCHAR, value VARCHAR)")
        con.execute(
            "INSERT INTO meta VALUES ('data_version', ?), ('pipeline_version', '2.0.0'), "
            "('built_at', '2026-10-20T15:19:06+00:00')",
            [version],
        )
        con.execute(f"CREATE TABLE balls AS SELECT range AS ball FROM range({rows})")


@pytest.fixture
def exports(tmp_path: Path) -> Path:
    folder = tmp_path / "exports"
    folder.mkdir()
    for name in ("serving.duckdb", "serving-test.duckdb", "players.duckdb"):
        database(folder / name)
    return folder


def test_packs_and_installs_every_database(exports: Path, tmp_path: Path) -> None:
    archive = tmp_path / "criciq-data.zip"
    manifest: dict[str, Any] = snapshot.pack(exports, archive)
    assert manifest["data_version"] == "2026-10-14.abc"
    assert manifest["pipeline_version"] == "2.0.0"
    assert set(manifest["files"]) == {"serving.duckdb", "serving-test.duckdb", "players.duckdb"}
    with zipfile.ZipFile(archive) as zf:
        assert {"manifest.json", "NOTICE.txt"} <= set(zf.namelist())
        assert "Cricsheet" in zf.read("NOTICE.txt").decode()

    target = tmp_path / "fresh" / "exports"
    # A database from an older snapshot that this one no longer has goes.
    target.mkdir(parents=True)
    (target / "serving-old.duckdb").write_bytes(b"old")
    installed = snapshot.install(archive, target, "2.0.0")
    assert installed["data_version"] == "2026-10-14.abc"
    assert sorted(p.name for p in target.glob("*.duckdb")) == [
        "players.duckdb",
        "serving-test.duckdb",
        "serving.duckdb",
    ]
    with duckdb.connect(str(target / "serving.duckdb"), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM balls").fetchone() == (3,)
    assert snapshot.installed(target)["data_version"] == "2026-10-14.abc"
    assert not list(target.glob(".incoming-*"))


def test_refuses_a_file_that_does_not_match_its_checksum(exports: Path, tmp_path: Path) -> None:
    archive = tmp_path / "criciq-data.zip"
    snapshot.pack(exports, archive)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item)
            dst.writestr(item, data + b"x" if item.filename == "players.duckdb" else data)
    target = tmp_path / "target"
    with pytest.raises(snapshot.SnapshotError, match="checksum"):
        snapshot.install(tampered, target, "2.0.0")
    # Nothing was put in place.
    assert not list(target.glob("*.duckdb"))


def test_refuses_data_from_another_pipeline_version(exports: Path, tmp_path: Path) -> None:
    archive = tmp_path / "criciq-data.zip"
    snapshot.pack(exports, archive)
    with pytest.raises(snapshot.SnapshotError, match=r"pipeline 2\.0\.0"):
        snapshot.install(archive, tmp_path / "target", "3.0.0")


def test_refuses_a_broken_zip(tmp_path: Path) -> None:
    broken = tmp_path / "criciq-data.zip"
    broken.write_bytes(b"not a zip")
    with pytest.raises(snapshot.SnapshotError, match="not a complete zip"):
        snapshot.install(broken, tmp_path / "target", "2.0.0")


def test_will_not_pack_databases_from_different_builds(exports: Path, tmp_path: Path) -> None:
    (exports / "serving-test.duckdb").unlink()
    database(exports / "serving-test.duckdb", version="2026-10-07.def")
    with pytest.raises(snapshot.SnapshotError, match="different builds"):
        snapshot.pack(exports, tmp_path / "criciq-data.zip")


def test_manifest_lists_sizes_and_checksums(exports: Path, tmp_path: Path) -> None:
    archive = tmp_path / "criciq-data.zip"
    snapshot.pack(exports, archive)
    with zipfile.ZipFile(archive) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    entry = manifest["files"]["serving.duckdb"]
    assert entry["bytes"] == (exports / "serving.duckdb").stat().st_size
    assert entry["sha256"] == snapshot.sha256(exports / "serving.duckdb")
