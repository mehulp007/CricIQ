import os
import sys


def test_numpy_runs_without_avx512_in_tests() -> None:
    # tests/__init__.py pins this before numpy loads, so model outputs match on every machine.
    assert os.environ["NPY_DISABLE_CPU_FEATURES"] == "X86_V4"
    assert "numpy" in sys.modules
