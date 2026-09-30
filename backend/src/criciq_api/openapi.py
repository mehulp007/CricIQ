"""Write the OpenAPI spec the frontend generates its types from.

Usage: uv run python -m criciq_api.openapi   (or `just api-types`)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from criciq_api.main import create_app
from criciq_core import paths

SPEC_PATH = paths.repo_root() / "frontend" / "lib" / "api" / "openapi.json"


def build_spec() -> dict[str, Any]:
    return create_app().openapi()


def render_spec() -> str:
    return json.dumps(build_spec(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    Path(SPEC_PATH).write_text(render_spec(), encoding="utf-8", newline="\n")
    print(f"wrote {SPEC_PATH}")


if __name__ == "__main__":
    main()
