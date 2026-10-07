"""Train a model group's models in order, then publish them to the site's data.

Usage (through uv, e.g. `just train-group leagues` and `just publish-models`):

    uv run python scripts/train_group.py train <group> [--only MODEL ...] [--fresh]
    uv run python scripts/train_group.py publish
    uv run python scripts/train_group.py status

A model group (config/model_groups.yaml: ipl, leagues, t20i, odi) has models of its
own, trained on its own competitions only. ``train`` runs every step for one group:

1. the ball-outcome model, win probability and the score projection
   (`criciq-ml train <model> --group <group>`);
2. scoring every competition, so the ratings see the new win probabilities;
3. the ratings, then the match simulator's backtest.

Each model is promoted only if it passes its gate; one that fails is kept on disk,
reported, and the run goes on. A new run names new versions (1.0.0 the first time,
then 1.1.0, 1.2.0, ...), writing them into the group's training configuration. A run
that stops part-way resumes where it left off: run the same command again (``--fresh``
starts over). Everything is logged, and ``data/training/<group>/summary.md`` says
what passed, by how much and how long it took.

``publish`` scores every competition with its group's current models, writes the
model cards and Model Insights data of every group with models of its own, and
re-exports the featured replays. Stop the local site (`just v2-up`) first: the
steps rewrite the files it serves.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from criciq_core import paths
from criciq_core.groups import ModelGroup, group, model_groups
from criciq_ml import formats, registry

ROOT = Path(__file__).resolve().parents[1]
# The order matters: the simulator plays with the ball model, and the ratings read
# the win probability added that scoring computes with the new model.
TRAINED_FIRST = ("ball_outcome", "win_probability", "score_projection")
TRAINED_AFTER_SCORING = ("ratings", "simulator")
MODELS = (*TRAINED_FIRST, *TRAINED_AFTER_SCORING)
LABELS = {
    "ball_outcome": "Next-ball model",
    "win_probability": "Win probability",
    "score_projection": "Score projection",
    "ratings": "Ratings",
    "simulator": "Simulator",
}
SITE_PORTS = (8000, 3000)
# Lines of a training run worth keeping in the summary.
KEY_LINE = re.compile(
    r"^\s*(test |\[gate\]|promoted|stability:|[A-Z0-9]{2,5}\s+(log loss|pinball)|.*borrows)"
)


def training_dir(group_id: str) -> Path:
    return paths.data_dir() / "training" / group_id


# --------------------------------------------------------------------------- running


def _environment() -> dict[str, str]:
    """The tools of this environment first on PATH (the simulator runs criciq-data)."""
    scripts = str(Path(sys.executable).parent)
    return {
        **os.environ,
        "PATH": scripts + os.pathsep + os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }


def _tool(name: str) -> str:
    found = shutil.which(name, path=_environment()["PATH"])
    if found is None:
        raise SystemExit(f"{name} not found: run this through `uv run` (or `just`)")
    return found


@dataclass
class Step:
    title: str
    exit_code: int
    seconds: float
    lines: list[str] = field(default_factory=list)


def run(title: str, command: list[str], log: Path) -> Step:
    """Run a command, echoing and logging its output as it comes."""
    print(f"\n== {title}", flush=True)
    started = time.monotonic()
    lines: list[str] = []
    with log.open("a", encoding="utf-8", newline="\n") as out:
        out.write(f"\n== {title}\n$ {' '.join(command)}\n")
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            out.write(line)
            lines.append(line.rstrip("\n"))
        code = process.wait()
        seconds = time.monotonic() - started
        out.write(f"== {title}: exit {code} after {seconds:.0f} s\n")
    print(f"== {title}: exit {code} after {_duration(seconds)}", flush=True)
    return Step(title, code, seconds, lines)


def _duration(seconds: float) -> str:
    minutes = round(seconds / 60)
    if minutes < 1:
        return f"{seconds:.0f} s"
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def keep_awake(on: bool) -> None:
    """Ask Windows not to sleep while this process runs (ignored elsewhere)."""
    if os.name != "nt":
        return
    es_continuous, es_system_required = 0x80000000, 0x00000001
    flags = es_continuous | (es_system_required if on else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


def site_running() -> list[int]:
    """The local site's ports in use (the API and the web app)."""
    busy = []
    for port in SITE_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
    return busy


def _require_site_stopped() -> None:
    busy = site_running()
    if busy:
        raise SystemExit(
            f"The local site is running (ports {', '.join(map(str, busy))}). Stop it first "
            "(Ctrl+C in the window running `just v2-up`), then run this again."
        )


class Lock:
    """One training or publishing run at a time (they share the data and the CPU)."""

    def __init__(self) -> None:
        self.path = paths.data_dir() / "training" / ".lock"

    def __enter__(self) -> Lock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            owner = self.path.read_text(encoding="utf-8").strip()
            if owner.isdigit() and _alive(int(owner)):
                raise SystemExit(
                    f"Another training or publishing run is going (process {owner}). Wait for "
                    "it to finish: two at once would compete for the CPU and the same files."
                )
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        return self

    def __exit__(self, *_: object) -> None:
        self.path.unlink(missing_ok=True)


def _alive(pid: int) -> bool:
    if os.name == "nt":
        found = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
        )
        return str(pid) in found.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# --------------------------------------------------------------------------- versions


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def next_version(configured: str, taken: list[str]) -> str:
    """The configured version if no model has it yet, else the next minor version
    after the newest one of the same major (1.0.0 taken: 1.1.0; 1.0.0 and 1.1.0: 1.2.0)."""
    if configured not in taken:
        return configured
    major = _version_key(configured)[0]
    minors = [_version_key(v)[1] for v in taken if _version_key(v)[0] == major]
    return f"{major}.{max(minors) + 1}.0"


def set_config_version(path: Path, version: str) -> None:
    """Write ``version`` into a training configuration, keeping its comments."""
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(r"(?m)^version: .*$", f"version: {version}", text, count=1)
    if count != 1:
        raise SystemExit(f"{path} has no `version:` line")
    path.write_text(updated, encoding="utf-8", newline="\n")


def config_version(path: Path) -> str:
    found = re.search(r"(?m)^version: (\S+)$", path.read_text(encoding="utf-8"))
    if found is None:
        raise SystemExit(f"{path} has no `version:` line")
    return found.group(1)


# --------------------------------------------------------------------------- state


@dataclass
class RunState:
    group: str
    started: str
    data_version: str
    versions: dict[str, str]
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    scored: bool = False
    scoring_seconds: float = 0.0
    finished: str | None = None

    @property
    def path(self) -> Path:
        return training_dir(self.group) / "state.json"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in self.__dict__.items()}
        self.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, group_id: str) -> RunState | None:
        path = training_dir(group_id) / "state.json"
        if not path.exists():
            return None
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def data_version() -> str:
    import duckdb

    con = duckdb.connect(str(paths.cricket_warehouse_path()), read_only=True)
    try:
        row = con.execute("SELECT value FROM meta WHERE key = 'data_version'").fetchone()
    finally:
        con.close()
    if row is None:
        raise SystemExit("the warehouse has no data version: build it first (`just v2-up`)")
    return str(row[0])


# --------------------------------------------------------------------------- train


def train(group_id: str, only: list[str] | None, fresh: bool) -> int:
    owner = _group(group_id)
    _require_site_stopped()
    if not paths.cricket_warehouse_path().exists():
        raise SystemExit("No warehouse yet: run `just v2-up --no-download` once first.")
    with Lock():
        keep_awake(True)
        try:
            return _train(owner, only, fresh)
        finally:
            keep_awake(False)


def _train(owner: ModelGroup, only: list[str] | None, fresh: bool) -> int:
    folder = training_dir(owner.id)
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "training.log"
    wanted = [m for m in MODELS if only is None or m in only]
    version_now = data_version()

    state = None if fresh else RunState.load(owner.id)
    resumable = (
        state is not None
        and state.finished is None
        and state.data_version == version_now
        and set(wanted) <= set(state.versions)
    )
    if resumable and state is not None:
        print(f"Resuming the run started {state.started} (pass --fresh to start over).")
    else:
        log.write_text("", encoding="utf-8")
        state = RunState(
            group=owner.id,
            started=_now(),
            data_version=version_now,
            versions=_name_versions(owner, wanted),
        )
        state.save()
    assert state is not None
    print(
        f"Training the {owner.id} group ({', '.join(owner.competitions)}) on data "
        f"{state.data_version}: " + ", ".join(f"{LABELS[m]} {state.versions[m]}" for m in wanted)
    )

    _ensure_copy(owner, log)
    ml = _tool("criciq-ml")
    for model in wanted:
        if model == "ratings" and not state.scored:
            # The ratings read the win probability added that scoring computes.
            step = run("scoring every competition (for the ratings)", [ml, "score"], log)
            if step.exit_code != 0:
                state.results["scoring"] = {"status": "error", "seconds": step.seconds}
                state.save()
                return _finish(owner, state, wanted)
            state.scored = True
            state.scoring_seconds = round(step.seconds)
            state.save()
        if state.results.get(model, {}).get("status") in ("promoted", "failed gate"):
            print(f"\n== {LABELS[model]} {state.versions[model]}: done earlier in this run")
            continue
        # --force: the version is this run's own, so a half-saved one from an
        # interrupted attempt is overwritten.
        step = run(
            f"{LABELS[model]} {state.versions[model]}",
            [ml, "train", model, "--group", owner.id, "--force"],
            log,
        )
        state.results[model] = {
            "status": _status(owner, model, state.versions[model], step),
            "seconds": round(step.seconds),
            "key_lines": [line for line in step.lines if KEY_LINE.match(line)][-40:],
            "tail": step.lines[-12:],
        }
        state.save()
    return _finish(owner, state, wanted)


def _name_versions(owner: ModelGroup, wanted: list[str]) -> dict[str, str]:
    """A new version for each model, written into the group's configuration."""
    versions = {}
    with formats.use_group(owner):
        for model in wanted:
            config = formats.config_path(model)
            configured = config_version(config)
            version = next_version(configured, registry.trained_versions(model))
            if version != configured:
                set_config_version(config, version)
            versions[model] = version
    return versions


def _ensure_copy(owner: ModelGroup, log: Path) -> None:
    """Build the warehouse copies if this group's is missing (after an upgrade)."""
    if paths.warehouse_path(owner.copy_name).exists():
        return
    step = run(
        f"building the warehouse copies ({owner.copy_name} is missing)",
        [_tool("criciq-data"), "build"],
        log,
    )
    if step.exit_code != 0 or not paths.warehouse_path(owner.copy_name).exists():
        raise SystemExit("Could not build the warehouse copies: see the log above.")


def _status(owner: ModelGroup, model: str, version: str, step: Step) -> str:
    with formats.use_group(owner):
        saved = version in registry.trained_versions(model)
        if model == "simulator":
            served = [
                c for c in owner.competitions if registry.current_version(model, c) == version
            ]
            promoted = bool(served)
        else:
            promoted = registry.current_version(model) == version
    if promoted:
        return "promoted"
    if saved:
        return "failed gate"
    return "error" if step.exit_code != 0 else "not promoted"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _finish(owner: ModelGroup, state: RunState, wanted: list[str]) -> int:
    state.finished = _now()
    state.save()
    text = summary(owner, state, wanted)
    folder = training_dir(owner.id)
    stamp = state.started.replace(":", "").replace("-", "")
    (folder / f"summary-{stamp}.md").write_text(text, encoding="utf-8", newline="\n")
    (folder / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    print("\n" + text)
    print(f"Summary: {folder / 'summary.md'}")
    print(f"Full log: {folder / 'training.log'}")
    failed = [m for m in wanted if state.results.get(m, {}).get("status") != "promoted"]
    return 1 if failed or "scoring" in state.results else 0


# --------------------------------------------------------------------------- summary


def summary(owner: ModelGroup, state: RunState, wanted: list[str]) -> str:
    total = sum(r.get("seconds", 0) for r in state.results.values()) + state.scoring_seconds
    lines = [
        f"# Training summary: the {owner.id} group",
        "",
        f"- Competitions: {', '.join(owner.competitions)} (trained on these only)",
        f"- Data version: {state.data_version}",
        f"- Started {state.started}, finished {state.finished} "
        f"(working time {_duration(total)}, scoring included)",
        "",
        "| Model | Version | Result | Time | Test result |",
        "|---|---|---|---|---|",
    ]
    for model in wanted:
        result = state.results.get(model, {})
        lines.append(
            f"| {LABELS[model]} | {state.versions[model]} | "
            f"{result.get('status', 'not run')} | {_duration(result.get('seconds', 0))} | "
            f"{_headline(owner, model, state.versions[model])} |"
        )
    if "scoring" in state.results:
        lines += ["", "**Scoring failed** before the ratings: see the log."]
    lines += ["", "## Details", ""]
    for model in wanted:
        done = state.results.get(model)
        if not done:
            continue
        lines += [f"### {LABELS[model]} {state.versions[model]}: {done['status']}", ""]
        lines += [*_details(owner, model, state.versions[model])]
        if done["status"] == "error":
            lines += ["Last lines of output:", "```", *done.get("tail", []), "```"]
        elif done.get("key_lines"):
            lines += ["```", *done["key_lines"], "```"]
        lines.append("")
    lines += [
        "## Next",
        "",
        "When every group you are training is done, run `just publish-models` to put the new "
        "models on the site's data, then review the results (Model Insights, the cards).",
        "",
    ]
    return "\n".join(lines)


def _evaluation(owner: ModelGroup, model: str, version: str) -> dict[str, Any] | None:
    with formats.use_group(owner):
        if version not in registry.trained_versions(model):
            return None
        return registry.load_evaluation(version, model)


def _headline(owner: ModelGroup, model: str, version: str) -> str:
    try:
        ev = _evaluation(owner, model, version)
        if ev is None:
            return "-"
        if model == "win_probability":
            t = ev["test"]
            gain = t["vs_baseline"]
            return (
                f"log loss {t['model']['log_loss']:.4f} vs baseline "
                f"{t['baseline']['log_loss']:.4f} (gain {gain['improvement']:+.4f}, 95% "
                f"{gain['ci_low']:+.4f} to {gain['ci_high']:+.4f}; {t['matches']} matches)"
            )
        if model == "score_projection":
            t = ev["test"]
            return (
                f"misses by {t['model']['mae']:.1f} runs vs par {t['par_baseline']['mae']:.1f}; "
                f"80% range holds {t['model']['coverage80']:.1%}"
            )
        if model == "ball_outcome":
            t = ev["test"]
            wins = sum(r["model_log_loss"] < r["baseline_log_loss"] for r in ev["backtest"])
            return (
                f"log loss {t['model']['log_loss']:.4f} vs baseline "
                f"{t['baseline']['log_loss']:.4f}; better in {wins} of "
                f"{len(ev['backtest'])} backtest years"
            )
        if model == "ratings":
            parts = ev.get("scopes", {"": ev}).values()
            levels = [c["stability"] for part in parts for c in part["components"]]
            return ", ".join(f"{levels.count(s)} {s}" for s in ("high", "moderate", "low"))
        if model == "simulator":
            with formats.use_group(owner):
                served = [
                    c for c in ev["competitions"] if registry.current_version(model, c) == version
                ]
            return f"served for {', '.join(served) or 'none'} of {', '.join(ev['competitions'])}"
    except (KeyError, TypeError, ValueError) as error:
        return f"see details ({type(error).__name__})"
    return "-"


def _details(owner: ModelGroup, model: str, version: str) -> list[str]:
    """Per-competition results and feature-selection hints from the evaluation."""
    ev = _evaluation(owner, model, version)
    if ev is None:
        return []
    out: list[str] = []
    try:
        if model in ("win_probability", "score_projection", "ball_outcome"):
            metric = "pinball" if model == "score_projection" else "log_loss"
            base = "par_baseline" if model == "score_projection" else "baseline"
            for line in ev["test"].get("by_competition", []):
                out.append(
                    f"- {line['competition']}: {metric} {line['model'][metric]:.4f} vs "
                    f"{line[base][metric]:.4f}"
                    + (f" ({line['matches']} matches)" if "matches" in line else "")
                )
        if model in ("win_probability", "score_projection"):
            out += _selection_hints(ev, model)
        if model == "simulator":
            for competition, part in ev["competitions"].items():
                first = part["first_innings"]
                out.append(
                    f"- {competition}: first-innings PIT chi-square {first['pit_chi2']:.1f} "
                    f"(limit {first['pit_chi2_critical']:.1f}), {part['matches']} test matches"
                )
    except (KeyError, TypeError) as error:
        out.append(f"- (details unavailable: {type(error).__name__} {error})")
    return [*out, ""] if out else []


def _selection_hints(ev: dict[str, Any], model: str) -> list[str]:
    """Candidate feature groups that beat the served set on the pre-test years."""
    rows = ev.get("feature_selection") or []
    metric = "pinball" if model == "score_projection" else "log_loss"
    hints = []
    if model == "win_probability":
        for innings in (1, 2):
            mine = [r for r in rows if r.get("innings_no") == innings]
            served = next((r for r in mine if r["variant"] == "served"), None)
            if served is None:
                continue
            better = [r for r in mine if r["variant"] != "served" and r[metric] < served[metric]]
            for r in sorted(better, key=lambda r: r[metric]):
                hints.append(
                    f"- Innings {innings}: {r['variant']} {r[metric]:.4f} vs served "
                    f"{served[metric]:.4f} on the pre-test years"
                )
    else:
        served = next((r for r in rows if r["variant"] == "served"), None)
        if served is not None:
            for r in sorted(rows, key=lambda r: r[metric]):
                if r["variant"] != "served" and r[metric] < served[metric]:
                    hints.append(
                        f"- {r['variant']} pinball {r[metric]:.3f} vs served "
                        f"{served[metric]:.3f} on the pre-test years"
                    )
    return (
        ["", "Feature candidates that beat the served set before the test years:", *hints]
        if (hints)
        else []
    )


# --------------------------------------------------------------------------- publish


def publish() -> int:
    _require_site_stopped()
    with Lock():
        keep_awake(True)
        try:
            return _publish()
        finally:
            keep_awake(False)


def _publish() -> int:
    folder = paths.data_dir() / "training"
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "publish.log"
    log.write_text("", encoding="utf-8")
    ml = _tool("criciq-ml")
    steps = [run("scoring every competition with its group's models", [ml, "score"], log)]
    fallbacks = [line.strip() for line in steps[0].lines if "[fallback]" in line]
    if steps[0].exit_code == 0:
        for owner in _reported_groups():
            steps.append(
                run(
                    f"model cards and insights: {owner.id}",
                    [ml, "report", "--group", owner.id],
                    log,
                )
            )
        steps.append(run("featured replays", [sys.executable, "-m", "criciq_api.featured"], log))
    failed = [s for s in steps if s.exit_code != 0]
    lines = [
        "# Publish summary",
        "",
        f"- Finished {_now()}",
        *[
            f"- {s.title}: {'ok' if s.exit_code == 0 else 'FAILED'} ({_duration(s.seconds)})"
            for s in steps
        ],
        "",
    ]
    if fallbacks:
        lines += [
            "Still scored with a pooled T20 model (their group has none of its own yet):",
            "",
            *[f"- {line.removeprefix('[fallback] ')}" for line in fallbacks],
            "",
        ]
    else:
        lines += ["Every competition is scored with its own group's models.", ""]
    lines += [
        "Next: review the summaries in data/training/. To look at the site locally, run "
        "`just v2-up --serve-only`.",
        "",
    ]
    text = "\n".join(lines)
    (folder / "publish-summary.md").write_text(text, encoding="utf-8", newline="\n")
    print("\n" + text)
    return 1 if failed else 0


def _reported_groups() -> list[ModelGroup]:
    """Groups with a model of their own (the IPL only once it is retrained here)."""
    found = []
    for owner in model_groups().groups:
        if owner.models == "" and not (training_dir(owner.id) / "state.json").exists():
            continue
        with formats.use_group(owner):
            if registry.current_version(registry.NAME) is not None:
                found.append(owner)
    return found


# --------------------------------------------------------------------------- status


def status() -> int:
    for owner in model_groups().groups:
        with formats.use_group(owner, serving=True):
            parts = []
            for model in MODELS:
                if model == "simulator":
                    parts.append(_simulators(owner))
                    continue
                competition = owner.competitions[0]
                version = registry.current_version(model, competition)
                fallback = registry.fallback_version(model, competition)
                parts.append(
                    f"{LABELS[model]} "
                    + ("none" if version is None else version)
                    + (" (pooled T20 fallback)" if fallback else "")
                )
        state = RunState.load(owner.id)
        last = (
            ""
            if state is None
            else f"\n    last run {state.started}"
            + (" (unfinished)" if state.finished is None else f", finished {state.finished}")
        )
        print(f"{owner.id} ({', '.join(owner.competitions)}):\n    " + "; ".join(parts) + last)
    return 0


def _simulators(owner: ModelGroup) -> str:
    """The simulator version serving each of a group's competitions (inside use_group)."""
    served = []
    for competition in owner.competitions:
        try:
            settings = registry.load_current_simulator(competition)
        except FileNotFoundError:
            continue
        covered = settings.manifest.get("competitions") or {"IPL": None}  # v1: the IPL's
        if competition in covered:
            fallback = registry.fallback_version(registry.SIMULATOR, competition)
            served.append(
                f"{competition} {settings.version}" + (" (pooled T20 fallback)" if fallback else "")
            )
    return "Simulator " + (", ".join(served) if served else "none")


def _group(value: str) -> ModelGroup:
    try:
        return group(value)
    except KeyError:
        known = ", ".join(g.id for g in model_groups().groups)
        raise SystemExit(f"Unknown group {value!r}: one of {known}.") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    trainer = sub.add_parser("train", help="train a model group's models in order")
    trainer.add_argument("group", help=", ".join(g.id for g in model_groups().groups))
    trainer.add_argument("--only", nargs="+", choices=MODELS, help="train only these models")
    trainer.add_argument("--fresh", action="store_true", help="start a new run, do not resume")
    sub.add_parser("publish", help="score, write model cards and featured replays")
    sub.add_parser("status", help="which models serve each group")
    args = parser.parse_args()
    if args.command == "train":
        return train(args.group, args.only, args.fresh)
    if args.command == "publish":
        return publish()
    return status()


if __name__ == "__main__":
    sys.exit(main())
