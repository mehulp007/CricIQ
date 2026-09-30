"""Assemble docs/images/frames/*.png into docs/images/replay.gif.

Usage: uv run --with pillow python scripts/make_gif.py
(frames come from frontend/scripts/capture-demo.mjs)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

IMAGES = Path(__file__).resolve().parents[1] / "docs" / "images"
FRAMES = IMAGES / "frames"
WIDTH = 960
FRAME_MS = 700
HOLD_LAST_MS = 3000


def main() -> None:
    paths = sorted(FRAMES.glob("*.png"))
    if not paths:
        raise SystemExit(f"no frames in {FRAMES}")
    frames = []
    for p in paths:
        with Image.open(p) as img:
            rgb = img.convert("RGB")
            height = round(rgb.height * WIDTH / rgb.width)
            frames.append(rgb.resize((WIDTH, height), Image.Resampling.LANCZOS))
    palette = frames[-1].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    durations = [FRAME_MS] * (len(quantized) - 1) + [HOLD_LAST_MS]
    target = IMAGES / "replay.gif"
    quantized[0].save(
        target,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    shutil.rmtree(FRAMES)
    print(f"wrote {target} ({target.stat().st_size / 1e6:.1f} MB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
