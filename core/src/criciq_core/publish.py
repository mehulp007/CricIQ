"""Put a freshly built database in place, even while the API has the old one open.

Builds write to a staging file and move it over the target in one step, so a
reader never sees a half-written database. On Windows a file that another
process has open cannot be replaced, and the local API keeps the serving
database open. In that case the new file is left beside the target as
``<name>.next``; the API swaps it in between requests (``criciq_api.db``) and
command-line readers already read it (``current``).
"""

from __future__ import annotations

import os
from pathlib import Path


def pending(target: Path) -> Path:
    """Where a new version waits while ``target`` is in use."""
    return target.with_name(target.name + ".next")


def current(target: Path) -> Path:
    """The newest published version of ``target`` (its pending file, if one waits)."""
    waiting = pending(target)
    return waiting if waiting.exists() else target


def publish(staging: Path, target: Path) -> Path:
    """Move ``staging`` over ``target``, or beside it if the target is in use.

    Returns where the file went.
    """
    try:
        os.replace(staging, target)
    except PermissionError:
        # Windows: the target is open in another process (the running API).
        os.replace(staging, pending(target))
        return pending(target)
    pending(target).unlink(missing_ok=True)  # an older version that never got swapped in
    return target
