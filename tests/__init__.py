"""Pin numpy to one set of CPU instructions before anything imports it.

numpy's Linux builds compute exp, log and log1p with Intel SVML on AVX-512
CPUs and with other code elsewhere, which differ in the last bit. A model
feature such as ``log1p(needed) - log1p(left)`` can then fall on the other side
of a tree split, so the same tests would score a few balls differently on
different machines (CI runners are a mix). Without AVX-512 every machine takes
the same path, which the IPL regression gate relies on.
"""

import os
import sys

if "numpy" in sys.modules and os.environ.get("NPY_DISABLE_CPU_FEATURES") != "X86_V4":
    raise RuntimeError("numpy was imported before tests/__init__.py could pin its CPU features")
os.environ.setdefault("NPY_DISABLE_CPU_FEATURES", "X86_V4")
