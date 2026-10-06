"""Pin numpy to one set of CPU instructions before anything imports it.

numpy's Linux builds compute exp, log and log1p with Intel SVML on AVX-512
CPUs and with other code elsewhere, which differ in the last bit. A model
feature such as ``log1p(needed) - log1p(left)`` can then fall on the other side
of a tree split, so the same tests would score a few balls differently on
different machines (CI runners are a mix). Without AVX-512 every Linux machine
takes the same path, so CI gives the same result on every runner. Windows and
Linux still round log1p differently on a few values; the IPL regression gate
allows for that (``criciq_pipelines.checksums``).
"""

import os
import sys

if "numpy" in sys.modules and os.environ.get("NPY_DISABLE_CPU_FEATURES") != "X86_V4":
    raise RuntimeError("numpy was imported before tests/__init__.py could pin its CPU features")
os.environ.setdefault("NPY_DISABLE_CPU_FEATURES", "X86_V4")
