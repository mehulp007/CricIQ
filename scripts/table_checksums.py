"""Content checksums of every table in a DuckDB file, for regression gates.

Usage: uv run python scripts/table_checksums.py <db.duckdb> [--against expected.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from criciq_pipelines.checksums import differences, table_checksums


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("--out", type=Path, help="write the checksums here")
    parser.add_argument("--against", type=Path, help="compare with saved checksums")
    args = parser.parse_args()
    result = table_checksums(args.db)
    if args.against:
        diff = differences(json.loads(args.against.read_text("utf-8")), result)
        print("\n".join(diff) if diff else "identical")
        return 1 if diff else 0
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
