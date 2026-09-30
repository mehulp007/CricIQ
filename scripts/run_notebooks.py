"""Execute notebooks in place so their outputs are stored (and render on GitHub).

Usage:  uv run --group notebooks python scripts/run_notebooks.py [notebook ...]

With no arguments every notebook in notebooks/ is executed in name order.
Notebooks read the local warehouse, so run `criciq-data run` first.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

NOTEBOOKS = Path(__file__).resolve().parents[1] / "notebooks"


def execute(path: Path) -> None:
    notebook = nbformat.read(path, as_version=4)
    NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOKS)}},
    ).execute()
    nbformat.write(notebook, path)
    print(f"executed {path.name}")


def main(argv: list[str]) -> None:
    targets = [Path(a) for a in argv] or sorted(NOTEBOOKS.glob("*.ipynb"))
    for path in targets:
        execute(path)


if __name__ == "__main__":
    main(sys.argv[1:])
