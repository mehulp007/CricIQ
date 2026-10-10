"""Time the local API's key endpoints for every competition (V2-8's performance check).

Usage:  uv run python scripts/perf.py [--base http://127.0.0.1:8000] [--repeat 20]

Each endpoint is called once cold (the first call builds whatever the API caches), then
``--repeat`` times warm; the warm p95 is the figure the performance target is about (under
300 ms for cached pages). One simulation per limited-overs competition is timed too (target:
under 2 s). Writes a Markdown table to stdout.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from typing import Any

COMPETITIONS = ("ipl", "bbl", "cpl", "psl", "sa20", "t20i", "odi", "test")
NATIONAL = ("t20i", "odi", "test")


def call(base: str, path: str, body: dict[str, Any] | None = None) -> tuple[float, Any]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base + path, data=data, headers={"content-type": "application/json"}
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read())
    return time.perf_counter() - started, payload


def endpoints(base: str, competition: str) -> list[str]:
    """The API calls behind each competition's key pages."""
    c = f"/api/v2/{competition}"
    _, matches = call(base, f"{c}/matches?page_size=24")
    match_id = matches["items"][0]["match_id"]
    _, teams = call(base, f"{c}/teams")
    team = teams["franchises"][0]["franchise_id"]
    _, players = call(base, f"{c}/players?page_size=30&sort=runs")
    player = players["items"][0]["player_id"]
    paths = [
        f"{c}/meta",
        f"{c}/matches?page_size=24",
        f"{c}/matches/{match_id}/timeline",
        f"{c}/players?page_size=30",
        f"{c}/players/{player}",
        f"{c}/players/{player}/splits",
        f"{c}/players/{player}/similar",
        f"/api/v2/players/{player}",
        f"/api/v2/players/{player}/ratings",
        f"{c}/matchups?page_size=25",
        f"{c}/teams",
        f"{c}/teams/{team}",
    ]
    if competition in NATIONAL:
        _, series = call(base, f"{c}/series?page_size=1")
        paths += [f"{c}/series", f"{c}/series/{series['items'][0]['event_id']}"]
    return paths


def simulate(base: str, competition: str) -> float | None:
    """Seconds for one 10,000-match simulation of the latest season's first two sides."""
    c = f"/api/v2/{competition}"
    try:
        _, seasons = call(base, f"{c}/simulate/seasons")
    except OSError:
        return None
    season = max(seasons, key=lambda s: s["season"])
    sides = []
    for entry in season["teams"][:2]:
        team = entry["team"]["franchise_id"]
        _, squad = call(base, f"{c}/simulate/squad/{season['season']}/{team}")
        sides.append({"franchise_id": team, "batters": squad["xi"], "bowlers": squad["bowlers"]})
    body = {"a": sides[0], "b": sides[1], "season": season["season"], "seed": 1}
    call(base, f"{c}/simulate/match", body)  # the first call builds the season's engine
    seconds, _ = call(base, f"{c}/simulate/match", {**body, "seed": 2})
    return seconds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--repeat", type=int, default=20)
    args = parser.parse_args()
    print("| Competition | Endpoint | Cold (ms) | Warm p95 (ms) |")
    print("|---|---|---|---|")
    worst: list[float] = []
    for competition in COMPETITIONS:
        for path in endpoints(args.base, competition):
            cold, _ = call(args.base, path)
            warm = sorted(call(args.base, path)[0] for _ in range(args.repeat))
            p95 = warm[max(0, round(0.95 * len(warm)) - 1)]
            worst.append(p95)
            short = path.replace(f"/api/v2/{competition}", "").replace("/api/v2", "") or "/"
            print(f"| {competition} | `{short}` | {1000 * cold:.0f} | {1000 * p95:.0f} |")
    print()
    median, top = 1000 * statistics.median(worst), 1000 * max(worst)
    print(f"Warm p95: median {median:.0f} ms, worst {top:.0f} ms")
    print()
    print("| Competition | Simulation of 10,000 matches (s) |")
    print("|---|---|")
    for competition in COMPETITIONS:
        if competition == "test":
            continue
        seconds = simulate(args.base, competition)
        print(f"| {competition} | {'-' if seconds is None else f'{seconds:.2f}'} |")


if __name__ == "__main__":
    main()
