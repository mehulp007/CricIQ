from criciq_api.openapi import SPEC_PATH, render_spec


def test_committed_openapi_spec_is_current() -> None:
    """The frontend's generated types come from this file; regenerate with `just api-types`."""
    assert SPEC_PATH.read_text(encoding="utf-8") == render_spec()
