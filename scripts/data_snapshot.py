"""The ready-built data CricIQ serves, packed into one zip and installed from it.

A first run should not have to rebuild the warehouse and score every ball to show the site:
the API reads only the exported databases (``serving*.duckdb`` per competition and
``players.duckdb``). They are published as ``criciq-data.zip`` on the repository's ``data``
release, refreshed weekly, and ``scripts/v2_up.py`` installs it.

Pack the current exports (for whoever publishes the data):

    uv run python scripts/data_snapshot.py pack

The zip holds the databases, ``manifest.json`` (data and pipeline versions, and every file's
size and SHA-256) and ``NOTICE.txt`` (the data's licences). Installing checks each file against
the manifest and refuses a snapshot built by a different pipeline version, whose tables the API
may not read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ASSET = "criciq-data.zip"
RELEASE_TAG = "data"
DEFAULT_URL = f"https://github.com/mehulp007/CricIQ/releases/download/{RELEASE_TAG}/{ASSET}"
MANIFEST = "manifest.json"
NOTICE = "NOTICE.txt"
# Written into the exports folder once a snapshot is installed: which one it was.
INSTALLED = "snapshot.json"

NOTICE_TEXT = """CricIQ data snapshot

Ball-by-ball data: Cricsheet (https://cricsheet.org), under the Open Data Commons Attribution
License (https://opendatacommons.org/licenses/by/1-0/).
Player attributes: Wikidata (https://www.wikidata.org, CC0) and English Wikipedia
(https://en.wikipedia.org, CC BY-SA 4.0).
Predictions: CricIQ's models (https://github.com/mehulp007/CricIQ, MIT).

Predictions and simulations are statistical estimates, not guarantees, and are not intended
for betting.
"""


class SnapshotError(Exception):
    """A snapshot that cannot be packed, downloaded or installed, with what to do about it."""


def snapshot_url() -> str:
    return os.environ.get("CRICIQ_DATA_URL", DEFAULT_URL)


def pipeline_version() -> str:
    try:
        return version("criciq-pipelines")
    except PackageNotFoundError:
        return "unknown"


def database_files(exports: Path) -> list[Path]:
    """The databases the API serves: one per competition, and the players database."""
    files = sorted(exports.glob("serving*.duckdb"))
    players = exports / "players.duckdb"
    if players.exists():
        files.append(players)
    return files


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_meta(path: Path) -> dict[str, str]:
    import duckdb

    with duckdb.connect(str(path), read_only=True) as con:
        rows = con.execute("SELECT key, value FROM meta").fetchall()
    return {str(key): str(value) for key, value in rows}


# --------------------------------------------------------------------------- pack


def pack(exports: Path, out: Path) -> dict[str, Any]:
    """Zip the exported databases with their manifest and notice; return the manifest."""
    files = database_files(exports)
    if not (exports / "serving.duckdb").exists() or not (exports / "players.duckdb").exists():
        raise SnapshotError(
            f"no complete export at {exports}: build the data first "
            "(uv run python scripts/v2_up.py --build-data)"
        )
    metas = {f.name: read_meta(f) for f in files}
    versions = {meta.get("data_version") for meta in metas.values()}
    if len(versions) != 1:
        raise SnapshotError(
            f"the databases come from different builds ({sorted(map(str, versions))}): "
            "rebuild them together before packing"
        )
    first = metas["serving.duckdb"]
    manifest: dict[str, Any] = {
        "data_version": first.get("data_version"),
        "pipeline_version": first.get("pipeline_version"),
        "built_at": first.get("built_at"),
        "packed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "files": {f.name: {"bytes": f.stat().st_size, "sha256": sha256(f)} for f in files},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".part")
    with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(MANIFEST, json.dumps(manifest, indent=2) + "\n")
        zf.writestr(NOTICE, NOTICE_TEXT)
        for f in files:
            zf.write(f, f.name)
    os.replace(partial, out)
    return manifest


# --------------------------------------------------------------------------- install


def download(url: str, dest: Path) -> None:
    """Fetch ``url`` to ``dest``, printing progress; a failed download leaves nothing behind."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as f:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            shown = -1
            started = time.monotonic()
            while chunk := response.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                step = done * 10 // total if total else done >> 24
                if step != shown:
                    shown = step
                    size = (
                        f"{done / 1e6:.0f} of {total / 1e6:.0f} MB"
                        if total
                        else f"{done / 1e6:.0f} MB"
                    )
                    print(f"  {size}  ({time.monotonic() - started:.0f} s)", flush=True)
        os.replace(partial, dest)
    except urllib.error.HTTPError as error:
        partial.unlink(missing_ok=True)
        if error.code == 404:
            raise SnapshotError(
                f"no data is published at {url} (yet). To build it on this computer instead "
                "(about 25 minutes), add --build-data."
            ) from error
        raise SnapshotError(f"could not download the data from {url} ({error})") from error
    except OSError as error:
        partial.unlink(missing_ok=True)
        raise SnapshotError(
            f"could not download the data from {url} ({error}). Check the internet connection "
            "and run the same command again; to build the data on this computer instead "
            "(about 25 minutes), add --build-data."
        ) from error


def read_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    try:
        manifest: dict[str, Any] = json.loads(zf.read(MANIFEST))
    except (KeyError, ValueError) as error:
        raise SnapshotError("the data zip has no readable manifest.json") from error
    return manifest


def install(archive: Path, exports: Path, expected_pipeline: str | None = None) -> dict[str, Any]:
    """Check ``archive`` against its manifest and put its databases in ``exports``.

    Nothing in ``exports`` changes unless every file checks out.
    """
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile as error:
        raise SnapshotError(f"{archive.name} is not a complete zip: download it again") from error
    with zf:
        manifest = read_manifest(zf)
        built_by = str(manifest.get("pipeline_version"))
        if expected_pipeline and built_by != expected_pipeline:
            raise SnapshotError(
                f"the data snapshot was built by pipeline {built_by}, but this code is pipeline "
                f"{expected_pipeline}: update the code (git pull), or build the data on this "
                "computer with --build-data"
            )
        files: dict[str, dict[str, Any]] = manifest.get("files", {})
        if "serving.duckdb" not in files or "players.duckdb" not in files:
            raise SnapshotError("the data zip is missing serving.duckdb or players.duckdb")
        exports.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=exports, prefix=".incoming-") as tmp:
            staging = Path(tmp)
            for name, expected in files.items():
                if Path(name).name != name or not name.endswith(".duckdb"):
                    raise SnapshotError(f"unexpected file in the data zip: {name}")
                target = staging / name
                with zf.open(name) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                if sha256(target) != expected.get("sha256"):
                    raise SnapshotError(f"{name} does not match its checksum: download it again")
            for name in files:
                os.replace(staging / name, exports / name)
    # A database left over from an older snapshot (or a pending swap) would be served too.
    for stale in exports.glob("serving*.duckdb*"):
        if stale.name not in files:
            stale.unlink(missing_ok=True)
    (exports / INSTALLED).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def installed(exports: Path) -> dict[str, Any] | None:
    """The manifest of the snapshot installed in ``exports``, if one was."""
    try:
        manifest: dict[str, Any] = json.loads((exports / INSTALLED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return manifest


def fetch(exports: Path, url: str | None = None) -> dict[str, Any]:
    """Download the published snapshot and install it in ``exports``."""
    url = url or snapshot_url()
    print(f"  from {url}", flush=True)
    exports.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=exports.parent, prefix=".download-") as tmp:
        archive = Path(tmp) / ASSET
        download(url, archive)
        print("  checking and unpacking", flush=True)
        return install(archive, exports, pipeline_version())


# --------------------------------------------------------------------------- command line


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack or install CricIQ's ready-built data.")
    sub = parser.add_subparsers(dest="command", required=True)
    pack_cmd = sub.add_parser("pack", help="zip the current exports for publishing")
    pack_cmd.add_argument("--exports", type=Path, default=ROOT / "data" / "exports")
    pack_cmd.add_argument("--out", type=Path, default=ROOT / "data" / "release" / ASSET)
    get_cmd = sub.add_parser("install", help="download the published data and install it")
    get_cmd.add_argument("--exports", type=Path, default=ROOT / "data" / "exports")
    get_cmd.add_argument("--url", default=None)
    args = parser.parse_args()

    try:
        if args.command == "pack":
            manifest = pack(args.exports, args.out)
            size = args.out.stat().st_size / 1e6
            print(
                f"packed {len(manifest['files'])} databases, data {manifest['data_version']} "
                f"(pipeline {manifest['pipeline_version']}), into {args.out} ({size:.0f} MB)\n\n"
                "To publish it: on GitHub, open Releases, then the release tagged "
                f"'{RELEASE_TAG}' (create it once, not marked as latest), delete its old "
                f"{ASSET} and upload this one with the same name."
            )
        else:
            manifest = fetch(args.exports, args.url)
            print(f"installed data {manifest['data_version']} in {args.exports}")
    except SnapshotError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
