"""Player attribute enrichment from open data (Wikidata + Wikipedia).

Cricsheet identifies every player but carries no biographical attributes.
This step links players through their ESPNcricinfo id (from Cricsheet's
register) to Wikidata, which supplies the full name, date of birth and
country, and to the player's English Wikipedia article, whose cricketer
infobox supplies batting hand and bowling style.

The output, ``reference/player_attributes.csv``, is committed so warehouse
builds stay offline and reproducible. Corrections go in
``reference/player_attributes_overrides.csv`` and are applied last.

Data licences: Wikidata is CC0; batting/bowling facts are extracted from
Wikipedia (CC BY-SA 4.0) and attributed in the README.
"""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from criciq_pipelines.raw import USER_AGENT

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

ATTRIBUTE_COLUMNS = (
    "player_id",
    "full_name",
    "date_of_birth",
    "country",
    "batting_hand",
    "bowling_arm",
    "bowling_type",
    "bowling_style",
    "source",
)


# --------------------------------------------------------------------------- parsing (pure)

_REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_LIST_TEMPLATE = re.compile(
    r"\{\{\s*(?:ubl|unbulleted list|plainlist|flatlist|hlist|nowrap|small|nobr)\s*\|([^{}]*)\}\}",
    re.I,
)
_ANY_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_TAG = re.compile(r"<[^>]+>")


def infobox_field(wikitext: str, name: str) -> str | None:
    """Plain-text value of ``| name = ...`` in a cricketer infobox, or None."""
    match = re.search(rf"^\s*\|\s*{re.escape(name)}\s*=(.*)$", wikitext, re.M | re.I)
    if not match:
        return None
    value = _COMMENT.sub("", _REF.sub("", match.group(1)))
    value = re.sub(r"<br\s*/?>", ", ", value, flags=re.I)
    value = _LINK.sub(r"\1", value)
    previous = None
    while previous != value:  # unwrap nested list/format templates, keeping the first item
        previous = value
        value = _LIST_TEMPLATE.sub(lambda m: m.group(1).split("|")[0], value)
    value = _ANY_TEMPLATE.sub("", _TAG.sub("", value))
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    return value or None


_COUNTRY_ALIASES = {
    "bharat": "India",
    "uae": "United Arab Emirates",
    "usa": "United States",
    "united states of america": "United States",
}


def normalize_country(text: str | None) -> str | None:
    """Tidy a country value: drop footnote digits and parentheticals, unify aliases."""
    if not text:
        return None
    value = re.split(r",", text)[0]
    value = re.sub(r"\([^)]*\)|\d+", "", value).strip()
    return _COUNTRY_ALIASES.get(value.lower(), value) or None


def normalize_batting(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if re.search(r"\bleft[\s-]*hand", lowered):
        return "left"
    if re.search(r"\bright[\s-]*hand", lowered):
        return "right"
    return None


@dataclass(frozen=True)
class BowlingStyle:
    arm: str | None
    kind: str | None  # "pace" | "spin"
    style: str | None  # canonical description, e.g. "Right-arm fast-medium"


_PACE_STYLES = (
    ("fast-medium", "fast-medium"),
    ("fast medium", "fast-medium"),
    ("medium-fast", "medium-fast"),
    ("medium fast", "medium-fast"),
    ("fast", "fast"),
    ("pace", "fast"),
    ("medium", "medium"),
    ("seam", "medium"),
)
_SPIN_STYLES = (
    ("unorthodox", "wrist spin"),
    ("chinaman", "wrist spin"),
    ("wrist", "wrist spin"),
    ("orthodox", "orthodox"),
    ("googly", "leg break"),
    ("leg break", "leg break"),
    ("legbreak", "leg break"),
    ("leg-break", "leg break"),
    ("leg spin", "leg break"),
    ("off break", "off break"),
    ("offbreak", "off break"),
    ("off-break", "off break"),
    ("off spin", "off break"),
    ("off-spin", "off break"),
    ("offspin", "off break"),
    ("leg-spin", "leg break"),
    ("legspin", "leg break"),
    ("slow left", "orthodox"),
    ("spin", "spin"),
)


def normalize_bowling(text: str | None) -> BowlingStyle:
    """Primary bowling style from an infobox value (first style listed wins)."""
    if not text:
        return BowlingStyle(None, None, None)
    primary = re.split(r",|/|;|\band\b|\n", text.lower())[0].strip()
    if not primary:
        return BowlingStyle(None, None, None)

    arm: str | None = None
    if re.search(r"\bleft[\s-]*arm|slow left|left-arm", primary):
        arm = "left"
    elif re.search(r"\bright[\s-]*arm", primary):
        arm = "right"

    for needle, style in _SPIN_STYLES:
        if needle in primary:
            if arm is None and style in ("off break", "leg break"):
                arm = "right"  # by convention these describe right-arm bowlers
            if arm is None and style == "orthodox":
                arm = "left"
            return BowlingStyle(arm, "spin", _describe(arm, style))
    for needle, style in _PACE_STYLES:
        if needle in primary:
            return BowlingStyle(arm, "pace", _describe(arm, style))
    return BowlingStyle(arm, None, None)


def _describe(arm: str | None, style: str) -> str:
    if arm is None:
        return style.capitalize()
    return f"{arm.capitalize()}-arm {style}"


# --------------------------------------------------------------------------- fetching (network)


# Wait before each retry of a request the server dropped, throttled or failed.
RETRY_DELAYS_SECONDS = (10.0, 30.0, 90.0)


def _get_json(
    url: str,
    timeout: float = 120.0,
    delays: Sequence[float] = RETRY_DELAYS_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(len(delays) + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            # Client errors other than throttling (429) will not go away on a retry.
            status = getattr(error, "code", None)
            permanent = status is not None and 400 <= status < 500 and status != 429
            if permanent or attempt == len(delays):
                raise
            sleep(delays[attempt])
    raise AssertionError("unreachable")


def _chunks(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def fetch_wikidata(cricinfo_ids: Sequence[str], pause: float = 1.0) -> dict[str, dict[str, str]]:
    """Wikidata facts keyed by ESPNcricinfo id (P2697)."""
    out: dict[str, dict[str, str]] = {}
    for chunk in _chunks(sorted(set(cricinfo_ids)), 200):
        values = " ".join(f'"{v}"' for v in chunk)
        query = f"""
        SELECT ?ci ?item ?itemLabel ?dob ?sportCountryLabel ?citizenLabel ?article WHERE {{
          VALUES ?ci {{ {values} }}
          ?item wdt:P2697 ?ci .
          OPTIONAL {{ ?item wdt:P569 ?dob }}
          OPTIONAL {{ ?item wdt:P1532 ?sportCountry }}
          OPTIONAL {{ ?item wdt:P27 ?citizen }}
          OPTIONAL {{ ?article schema:about ?item ;
                               schema:isPartOf <https://en.wikipedia.org/> }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul". }}
        }}"""
        url = f"{WIKIDATA_SPARQL}?format=json&query={urllib.parse.quote(query)}"
        for binding in _get_json(url)["results"]["bindings"]:
            ci = binding["ci"]["value"]
            record = out.setdefault(ci, {})
            record.setdefault("qid", binding["item"]["value"].rsplit("/", 1)[-1])
            record.setdefault("label", binding["itemLabel"]["value"])
            if "dob" in binding:
                record.setdefault("dob", binding["dob"]["value"][:10])
            if "sportCountryLabel" in binding:
                record.setdefault("sport_country", binding["sportCountryLabel"]["value"])
            if "citizenLabel" in binding:
                record.setdefault("citizenship", binding["citizenLabel"]["value"])
            if "article" in binding:
                title = binding["article"]["value"].rsplit("/wiki/", 1)[-1]
                record.setdefault("enwiki", urllib.parse.unquote(title).replace("_", " "))
        time.sleep(pause)
    return out


def fetch_wikitext(titles: Sequence[str], pause: float = 0.5) -> dict[str, str]:
    """Current wikitext for English Wikipedia titles (redirects followed)."""
    out: dict[str, str] = {}
    for chunk in _chunks(sorted(set(titles)), 50):
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "redirects": "1",
            "titles": "|".join(chunk),
        }
        data = _get_json(f"{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}")["query"]
        texts = {
            page["title"]: page["revisions"][0]["slots"]["main"]["content"]
            for page in data.get("pages", [])
            if page.get("revisions")
        }
        aliases = {
            entry["from"]: entry["to"]
            for entry in data.get("normalized", []) + data.get("redirects", [])
        }
        for title in chunk:
            resolved = title
            for _ in range(3):
                resolved = aliases.get(resolved, resolved)
            if resolved in texts:
                out[title] = texts[resolved]
        time.sleep(pause)
    return out


# --------------------------------------------------------------------------- assembly


def build_rows(
    players: Sequence[tuple[str, str]],
    wikidata: dict[str, dict[str, str]],
    wikitext: dict[str, str],
) -> list[dict[str, str]]:
    """Attribute rows for (player_id, cricinfo_id) pairs."""
    rows = []
    for player_id, cricinfo_id in sorted(players):
        facts = wikidata.get(cricinfo_id, {})
        title = facts.get("enwiki")
        text = wikitext.get(title, "") if title else ""
        bowling = (
            normalize_bowling(infobox_field(text, "bowling"))
            if text
            else BowlingStyle(None, None, None)
        )
        provenance = [p for p in (facts.get("qid"), f"enwiki:{title}" if title else None) if p]
        rows.append(
            {
                "player_id": player_id,
                "full_name": _strip_disambiguation(facts.get("label", ""))
                or _strip_disambiguation(title or ""),
                "date_of_birth": facts.get("dob", ""),
                # The infobox names the international side a player represents,
                # which is what IPL overseas status depends on. Wikidata
                # citizenship is only a fallback: it is sparser and less reliable.
                "country": normalize_country(
                    (infobox_field(text, "country") if text else None)
                    or facts.get("sport_country")
                    or facts.get("citizenship")
                )
                or "",
                "batting_hand": (
                    normalize_batting(infobox_field(text, "batting")) if text else None
                )
                or "",
                "bowling_arm": bowling.arm or "",
                "bowling_type": bowling.kind or "",
                "bowling_style": bowling.style or "",
                "source": " | ".join(provenance),
            }
        )
    return rows


def _strip_disambiguation(label: str) -> str:
    # Wikidata labels are plain names, but guard against "Name (cricketer)" forms
    # and labels that are just the Q-id when no English label exists.
    if re.fullmatch(r"Q\d+", label):
        return ""
    return re.sub(r"\s*\([^)]*\)$", "", label)


def apply_overrides(rows: list[dict[str, str]], overrides_csv: Path) -> int:
    """Apply manual corrections (player_id, field, value, note). Returns count applied."""
    if not overrides_csv.exists():
        return 0
    by_id = {row["player_id"]: row for row in rows}
    applied = 0
    with overrides_csv.open(encoding="utf-8", newline="") as fh:
        for override in csv.DictReader(fh):
            row = by_id.get(override["player_id"])
            field = override["field"]
            if row is None or field not in ATTRIBUTE_COLUMNS or field in ("player_id", "source"):
                raise ValueError(f"invalid override: {override}")
            row[field] = override["value"]
            if not row["source"].endswith("manual"):
                row["source"] = (row["source"] + " | manual").strip(" |")
            applied += 1
    return applied


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    """Rows of an attributes file keyed by player id (empty if there is none)."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["player_id"]: row for row in csv.DictReader(fh)}


def write_rows(rows: Sequence[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ATTRIBUTE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
