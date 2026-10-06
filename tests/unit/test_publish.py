import os
from pathlib import Path

import pytest

from criciq_core import publish


def test_publish_replaces_the_target(tmp_path: Path) -> None:
    target, staging = tmp_path / "serving.duckdb", tmp_path / "new"
    target.write_text("old")
    publish.pending(target).write_text("stale")
    staging.write_text("new")
    assert publish.publish(staging, target) == target
    assert target.read_text() == "new"
    assert not publish.pending(target).exists()  # an older waiting version is dropped
    assert publish.current(target) == target


def test_publish_waits_beside_a_target_in_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, staging = tmp_path / "serving.duckdb", tmp_path / "new"
    target.write_text("old")
    staging.write_text("new")
    real_replace = os.replace

    def locked(src: str | Path, dst: str | Path) -> None:
        if Path(dst) == target:  # what Windows does while the API has the file open
            raise PermissionError(5, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", locked)
    assert publish.publish(staging, target) == publish.pending(target)
    assert target.read_text() == "old"
    assert publish.current(target).read_text() == "new"
