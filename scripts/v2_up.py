"""CricIQ on your machine: build every competition, score, then serve the API and the web app.

Usage:  uv run python scripts/v2_up.py [--no-download] [--serve-only] [--dev]   (or `just v2-up`)

1. ``criciq-data run`` downloads the Cricsheet archives of every competition in
   config/competitions.yaml, builds and validates the full warehouse, and exports a
   serving database per competition and the players database.
2. ``criciq-ml score`` adds every ball's predictions with the committed models.
3. The API starts on port 8000; once it answers, the web app is built for production
   (only when its sources changed since the last build: the build pre-renders pages
   from the API) and served on port 3000. ``--dev`` serves the Next.js dev server
   instead, for working on the web app. Ctrl+C stops both. Open http://localhost:3000.

``--serve-only`` skips steps 1 and 2 and serves the data already built. The
data-quality reports go to data/data-quality-report.md and data/data-quality/ so local
runs never touch the committed ones in docs/.
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

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("CRICIQ_DATA_DIR", ROOT / "data"))
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


def tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise SystemExit(f"{name} not found on PATH (run through `uv run` / `just v2-up`)")
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


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def preflight(serve_only: bool) -> None:
    """Fail early, with what to do, rather than half-way through."""
    problems = []
    for port, what in ((API_PORT, "API"), (WEB_PORT, "web app")):
        if port_in_use(port):
            problems.append(
                f"port {port} (the {what}) is already in use: is CricIQ already running? "
                "Stop it (Ctrl+C in its window) or the program using the port."
            )
    serving = DATA / "exports" / "serving.duckdb"
    if (
        serve_only
        and not serving.exists()
        and not serving.with_name("serving.duckdb.next").exists()
    ):
        problems.append(
            f"no data at {serving.parent}: run `just v2-up` once without --serve-only to "
            "download and build it."
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


def build_is_current() -> bool:
    build_id = FRONTEND / ".next" / "BUILD_ID"
    return build_id.exists() and build_id.stat().st_mtime >= newest_source()


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
    parser = argparse.ArgumentParser(description="Build every competition, score and serve.")
    parser.add_argument(
        "--no-download", action="store_true", help="rebuild from the latest local snapshot"
    )
    parser.add_argument("--serve-only", action="store_true", help="skip the build and scoring")
    parser.add_argument(
        "--dev", action="store_true", help="serve the Next.js dev server, not a production build"
    )
    args = parser.parse_args()

    env = dict(os.environ)
    env.pop("CRICIQ_COMPETITIONS", None)  # every configured competition
    env.setdefault("PYTHONIOENCODING", "utf-8")
    preflight(args.serve_only)
    if not args.serve_only:
        run = [tool("criciq-data"), "run", "--report", str(DATA / "data-quality-report.md")]
        if args.no_download:
            run.append("--no-download")
        step("data: every competition", run, env)
        step("models: score every ball", [tool("criciq-ml"), "score"], env)
        report_disk()
    return serve(env, args.dev)


if __name__ == "__main__":
    raise SystemExit(main())
