"""The v2 local runtime: build every competition, score, then serve the API and the web app.

Usage:  uv run python scripts/v2_up.py [--no-download] [--serve-only]   (or `just v2-up`)

1. ``criciq-data run`` downloads the Cricsheet archives of every competition in
   config/competitions.yaml, builds and validates the full warehouse, and exports
   the IPL serving database (the site serves IPL until the switcher lands) and the
   players database (every T20 competition's Player Lab, under /api/v2).
2. ``criciq-ml score`` adds every ball's predictions with the committed models.
3. The API (port 8000) and the Next.js dev server (port 3000) start together;
   Ctrl+C stops both. Open http://localhost:3000 (not 127.0.0.1: the dev server
   only hydrates on localhost).

The data-quality reports go to data/data-quality-report.md and data/data-quality/
so local runs never touch the committed ones in docs/.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("CRICIQ_DATA_DIR", ROOT / "data"))
API_PORT, WEB_PORT = 8000, 3000
WINDOWS = os.name == "nt"


def tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise SystemExit(f"{name} not found on PATH (run through `uv run` / `just v2-up`)")
    return found


def step(title: str, command: list[str], env: dict[str, str]) -> None:
    print(f"\n== {title}", flush=True)
    started = time.monotonic()
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    print(f"== {title}: {time.monotonic() - started:.0f} s", flush=True)


def folder_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0


def report_disk() -> None:
    print("\n== local data on disk")
    for name in ("raw", "interim", "warehouse", "exports"):
        print(f"  {name:<10} {folder_size(DATA / name) / 1e9:6.2f} GB")
    print(f"  {'total':<10} {folder_size(DATA) / 1e9:6.2f} GB")


def wait_for(url: str, seconds: int) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5):
                return True
        except OSError:
            time.sleep(1)
    return False


def start(command: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    if WINDOWS:
        return subprocess.Popen(
            command, cwd=ROOT, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    return subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True)


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


def serve(env: dict[str, str]) -> int:
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
        web = start([tool("pnpm"), "--dir", "frontend", "dev", "--port", str(WEB_PORT)], web_env)
        if not wait_for(f"http://localhost:{WEB_PORT}", 180):
            print("the web app did not start; see its output above", file=sys.stderr)
            return 1
        print(
            f"\n== CricIQ v2 is up: http://localhost:{WEB_PORT}  "
            f"(API http://localhost:{API_PORT}/docs). Ctrl+C stops both.",
            flush=True,
        )
        while api.poll() is None and web.poll() is None:
            time.sleep(1)
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
    args = parser.parse_args()

    env = dict(os.environ)
    env.pop("CRICIQ_COMPETITIONS", None)  # every configured competition
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if not args.serve_only:
        run = [tool("criciq-data"), "run", "--report", str(DATA / "data-quality-report.md")]
        if args.no_download:
            run.append("--no-download")
        step("data: every competition", run, env)
        step("models: score every ball", [tool("criciq-ml"), "score"], env)
        report_disk()
    return serve(env)


if __name__ == "__main__":
    raise SystemExit(main())
