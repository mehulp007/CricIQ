"""Raw data snapshots: download Cricsheet files and store them immutably.

Every snapshot lives in ``data/raw/<data_version>/`` with a ``manifest.json``:
one or more match archives (one per competition, e.g. ``ipl_json.zip``) and
the people register. The version is derived from the *content* (date of the
latest match + a hash of the files), so re-downloading unchanged data yields
the same version and every downstream artifact can be traced back to exact
inputs. Which archive a match came from does not matter downstream: the
warehouse assigns competitions from each match's own details.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from criciq_core import paths

USER_AGENT = "CricIQ-data-pipeline/0.1 (+https://github.com/mehulp007/CricIQ)"

DOWNLOADS = "https://cricsheet.org/downloads/"
PEOPLE_URL = "https://cricsheet.org/register/people.csv"
PEOPLE = "people.csv"
LATEST_POINTER = "LATEST"

_README_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}) - ", re.MULTILINE)


@dataclass(frozen=True)
class RawSnapshot:
    version: str
    directory: Path

    @property
    def archives(self) -> list[Path]:
        """The snapshot's match archives, in name order."""
        return sorted(self.directory.glob("*.zip"))

    @property
    def people(self) -> Path:
        return self.directory / PEOPLE

    @property
    def manifest(self) -> dict[str, object]:
        with (self.directory / "manifest.json").open(encoding="utf-8") as fh:
            data: dict[str, object] = json.load(fh)
        return data


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


_sha256 = file_sha256


def latest_match_date(archive: Path) -> dt.date:
    """Latest match date in a Cricsheet archive (read from its README, else the JSON)."""
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if "README.txt" in names:
            dates = _README_DATE.findall(zf.read("README.txt").decode("utf-8"))
            if dates:
                return max(dt.date.fromisoformat(d) for d in dates)
        latest: dt.date | None = None
        for name in names:
            if name.endswith(".json"):
                info = json.loads(zf.read(name))["info"]
                day = dt.date.fromisoformat(info["dates"][0])
                latest = day if latest is None or day > latest else latest
    if latest is None:
        raise ValueError(f"{archive} contains no matches")
    return latest


def compute_version(archives: list[Path], people: Path) -> str:
    """Latest match date + a hash of every file (archives in name order).

    With a single archive this is the hash of that archive and the register, so a
    one-competition snapshot keeps the version it always had."""
    ordered = sorted(archives, key=lambda p: p.name)
    combined = hashlib.sha256(
        ("".join(_sha256(a) for a in ordered) + _sha256(people)).encode()
    ).hexdigest()
    latest = max(latest_match_date(a) for a in ordered)
    return f"{latest.isoformat()}.{combined[:8]}"


def store_snapshot(
    archives: list[Path] | Path,
    people: Path,
    raw_root: Path | None = None,
    *,
    source: str = "local",
) -> RawSnapshot:
    """Copy source files into a versioned snapshot directory and mark it latest."""
    archives = [archives] if isinstance(archives, Path) else list(archives)
    if not archives:
        raise ValueError("a snapshot needs at least one match archive")
    names = [a.name for a in archives]
    if len(names) != len(set(names)):
        raise ValueError(f"archive names must be unique: {names}")
    root = raw_root or paths.raw_dir()
    version = compute_version(archives, people)
    target = root / version
    if not target.exists():
        staging = Path(tempfile.mkdtemp(prefix=".incoming-", dir=_ensure(root)))
        for archive in archives:
            shutil.copy2(archive, staging / archive.name)
        shutil.copy2(people, staging / PEOPLE)
        match_files = {}
        for name in sorted(names):
            with zipfile.ZipFile(staging / name) as zf:
                match_files[name] = sum(1 for n in zf.namelist() if n.endswith(".json"))
        manifest = {
            "data_version": version,
            "source": source,
            "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "latest_match_date": max(
                latest_match_date(staging / name) for name in names
            ).isoformat(),
            "match_files": match_files,
            "files": {
                name: {"sha256": _sha256(staging / name), "bytes": (staging / name).stat().st_size}
                for name in (*sorted(names), PEOPLE)
            },
            "urls": (
                {**{n: DOWNLOADS + n for n in sorted(names)}, PEOPLE: PEOPLE_URL}
                if source == "cricsheet"
                else {}
            ),
            "license": "Cricsheet data: Open Data Commons Attribution License (ODC-BY 1.0)",
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
        staging.rename(target)
    (root / LATEST_POINTER).write_text(version + "\n", encoding="utf-8")
    return RawSnapshot(version=version, directory=target)


def download(
    archives: list[str], raw_root: Path | None = None, timeout: float = 300.0
) -> RawSnapshot:
    """Download the named Cricsheet archives and the register as a snapshot."""
    root = raw_root or paths.raw_dir()
    with tempfile.TemporaryDirectory(prefix=".download-", dir=_ensure(root)) as tmp:
        sources = {**{name: DOWNLOADS + name for name in archives}, PEOPLE: PEOPLE_URL}
        for name, url in sources.items():
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with (
                urllib.request.urlopen(request, timeout=timeout) as response,
                (Path(tmp) / name).open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
        return store_snapshot(
            [Path(tmp) / name for name in archives], Path(tmp) / PEOPLE, root, source="cricsheet"
        )


def latest_snapshot(raw_root: Path | None = None) -> RawSnapshot:
    root = raw_root or paths.raw_dir()
    pointer = root / LATEST_POINTER
    if not pointer.exists():
        raise FileNotFoundError(f"no raw snapshot in {root}; run `criciq-data download` first")
    version = pointer.read_text(encoding="utf-8").strip()
    return RawSnapshot(version=version, directory=root / version)


def _ensure(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory
