"""CricIQ on your machine: get the data, then serve the API and the web app.

Usage:  uv run python scripts/v2_up.py [--update-data | --build-data [--no-download]]
                                      [--serve-only] [--dev]          (or `just v2-up`)

Before anything slow, it checks that Node.js and pnpm are installed and the ports are free,
and installs the web app's dependencies when they are missing or out of date.

1. The data. On the first run it downloads the ready-built databases the site serves (one per
   competition and the players database, about 150 MB, refreshed weekly) from the repository's
   ``data`` release and checks them (scripts/data_snapshot.py). After that it uses what is
   there; ``--update-data`` fetches the latest week's.
   ``--build-data`` builds them here instead, as the project does (about 25 minutes, all CPU
   cores): ``criciq-data run`` downloads the Cricsheet archives of every competition in
   config/competitions.yaml, builds and validates the full warehouse and exports the
   databases, then ``criciq-ml score`` adds every ball's predictions with the committed
   models. ``--no-download`` rebuilds from the Cricsheet archives already downloaded.
2. The API starts on port 8000; once it answers, the web app is built for production (only
   when its sources or the data changed since the last build: the build pre-renders pages
   from the API) and served on port 3000. ``--dev`` serves the Next.js dev server instead,
   for working on the web app. Ctrl+C stops both. Open http://localhost:3000.

``--serve-only`` never touches the data: it serves what is there. A local build's
data-quality reports go to data/data-quality-report.md and data/data-quality/ so local runs
never touch the committed ones in docs/.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import data_snapshot

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("CRICIQ_DATA_DIR", ROOT / "data"))
EXPORTS = DATA / "exports"
FRONTEND = ROOT / "frontend"
API_PORT, WEB_PORT = 8000, 3000
WINDOWS = os.name == "nt"
# What a production build of the web app is made from: a change to any of these rebuilds it.
WEB_SOURCES = (
    "app",
    "components",
    "lib",
    "data",
    "public",
    "next.config.ts",
    "package.json",
    "pnpm-lock.yaml",
    "postcss.config.mjs",
    "tsconfig.json",
)


RUN = "uv run python scripts/v2_up.py"
# What to do when a program is missing, in plain terms.
MISSING = {
    "node": "Node.js is not installed: install Node.js 24 (LTS) from https://nodejs.org, "
    "then open a new terminal.",
    "pnpm": "pnpm is not installed: run `npm install -g pnpm` (in PowerShell, if npm is "
    "blocked: `npm.cmd install -g pnpm`), then open a new terminal.",
}


def tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise SystemExit(MISSING.get(name, f"{name} not found: start this script with `{RUN}`"))
    return found


def step(title: str, command: list[str], env: dict[str, str]) -> None:
    print(f"\n== {title}", flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"\n== {title} failed (exit code {result.returncode}); see the output above"
        )
    print(f"== {title}: {time.monotonic() - started:.0f} s", flush=True)


def folder_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0


def report_disk() -> None:
    print("\n== local data on disk")
    for name in ("raw", "interim", "warehouse", "exports"):
        print(f"  {name:<10} {folder_size(DATA / name) / 1e9:6.2f} GB")
    print(f"  {'total':<10} {folder_size(DATA) / 1e9:6.2f} GB")


def has_data() -> bool:
    serving = EXPORTS / "serving.duckdb"
    return (EXPORTS / "players.duckdb").exists() and (
        serving.exists() or serving.with_name("serving.duckdb.next").exists()
    )


def get_data(update: bool) -> None:
    """Install the published, ready-built data on the first run, or when asked to update."""
    current = data_snapshot.installed(EXPORTS)
    if has_data() and not update:
        if current:
            print(f"\n== data: {current['data_version']} (--update-data gets the latest)")
        return
    print("\n== data: download the ready-built databases", flush=True)
    started = time.monotonic()
    try:
        manifest = data_snapshot.fetch(EXPORTS)
    except data_snapshot.SnapshotError as error:
        raise SystemExit(f"\n== data: {error}") from error
    print(
        f"== data: {manifest['data_version']} installed ({time.monotonic() - started:.0f} s)",
        flush=True,
    )


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def preflight(serve_only: bool) -> None:
    """Fail early, with what to do, rather than half-way through."""
    problems = [MISSING[name] for name in ("node", "pnpm") if shutil.which(name) is None]
    for port, what in ((API_PORT, "API"), (WEB_PORT, "web app")):
        if port_in_use(port):
            problems.append(
                f"port {port} (the {what}) is already in use: is CricIQ already running? "
                "Stop it (Ctrl+C in its window) or the program using the port."
            )
    if serve_only and not has_data():
        problems.append(
            f"no data at {EXPORTS} yet: run `{RUN}` once without --serve-only to download it."
        )
    if problems:
        raise SystemExit("cannot start:\n- " + "\n- ".join(problems))


def wait_for(url: str, seconds: int) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5):
                return True
        except OSError:
            time.sleep(1)
    return False


def start(command: list[str], env: dict[str, str], cwd: Path = ROOT) -> subprocess.Popen[bytes]:
    if WINDOWS:
        return subprocess.Popen(
            command, cwd=cwd, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)


def stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if WINDOWS:
        # pnpm and next spawn children: end the whole tree.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=30)


def newest_source() -> float:
    """The latest change to anything a production build of the web app is made from."""
    newest = 0.0
    for name in WEB_SOURCES:
        path = FRONTEND / name
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    newest = max(newest, f.stat().st_mtime)
    return newest


def ensure_web_dependencies(env: dict[str, str]) -> None:
    """Install the web app's packages on the first run, or after its lockfile changes."""
    installed = FRONTEND / "node_modules" / ".modules.yaml"
    lockfile = FRONTEND / "pnpm-lock.yaml"
    if installed.exists() and installed.stat().st_mtime >= lockfile.stat().st_mtime:
        return
    step(
        "web app: install packages",
        [tool("pnpm"), "--dir", "frontend", "install", "--frozen-lockfile"],
        env,
    )


def newest_data() -> float:
    """When the served data last changed: pages are pre-rendered from it."""
    return max((f.stat().st_mtime for f in EXPORTS.glob("*.duckdb")), default=0.0)


def build_is_current() -> bool:
    build_id = FRONTEND / ".next" / "BUILD_ID"
    return build_id.exists() and build_id.stat().st_mtime >= max(newest_source(), newest_data())


def serve(env: dict[str, str], dev: bool) -> int:
    api = start(
        [tool("uvicorn"), "criciq_api.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        env,
    )
    web = None
    try:
        if not wait_for(f"http://127.0.0.1:{API_PORT}/healthz", 120):
            print("the API did not start; see its output above", file=sys.stderr)
            return 1
        web_env = {**env, "CRICIQ_API_URL": f"http://127.0.0.1:{API_PORT}"}
        pnpm = tool("pnpm")
        if dev:
            web = start([pnpm, "--dir", "frontend", "dev", "--port", str(WEB_PORT)], web_env)
        else:
            if build_is_current():
                print("\n== web app: the production build is up to date", flush=True)
            else:
                step("web app: production build", [pnpm, "--dir", "frontend", "build"], web_env)
            web = start([pnpm, "--dir", "frontend", "start", "--port", str(WEB_PORT)], web_env)
        if not wait_for(f"http://localhost:{WEB_PORT}", 180):
            print("the web app did not start; see its output above", file=sys.stderr)
            return 1
        mode = "dev server" if dev else "production build"
        print(
            f"\n== CricIQ is up ({mode}): http://localhost:{WEB_PORT}  "
            f"(API http://localhost:{API_PORT}/docs). Ctrl+C stops both.",
            flush=True,
        )
        while api.poll() is None and web.poll() is None:
            time.sleep(1)
        print("\n== the API or the web app stopped; see the output above", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in (web, api):
            if process is not None:
                stop(process)


def main() -> int:
    parser = argparse.ArgumentParser(description="Get CricIQ's data, then serve the site.")
    data = parser.add_mutually_exclusive_group()
    data.add_argument(
        "--update-data", action="store_true", help="download the latest ready-built data"
    )
    data.add_argument(
        "--build-data",
        action="store_true",
        help="build and score every competition here (about 25 minutes)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="with --build-data: rebuild from the Cricsheet archives already downloaded",
    )
    parser.add_argument("--serve-only", action="store_true", help="serve the data already here")
    parser.add_argument(
        "--dev", action="store_true", help="serve the Next.js dev server, not a production build"
    )
    args = parser.parse_args()
    if args.no_download and not args.build_data:
        parser.error("--no-download goes with --build-data")
    if args.serve_only and (args.build_data or args.update_data):
        parser.error("--serve-only serves the data already here: drop it to get new data")

    env = dict(os.environ)
    env.pop("CRICIQ_COMPETITIONS", None)  # every configured competition
    env.setdefault("PYTHONIOENCODING", "utf-8")
    preflight(args.serve_only)
    ensure_web_dependencies(env)
    if args.build_data:
        run = [tool("criciq-data"), "run", "--report", str(DATA / "data-quality-report.md")]
        if args.no_download:
            run.append("--no-download")
        step("data: every competition", run, env)
        step("models: score every ball", [tool("criciq-ml"), "score"], env)
        # Built here, so no longer the published snapshot.
        (EXPORTS / data_snapshot.INSTALLED).unlink(missing_ok=True)
        report_disk()
    elif not args.serve_only:
        get_data(args.update_data)
    return serve(env, args.dev)


if __name__ == "__main__":
    raise SystemExit(main())
