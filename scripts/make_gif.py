"""Assemble docs/images/frames/*.png into docs/images/demo.gif, the README's tour.

Usage: uv run --with pillow python scripts/make_gif.py
(frames come from frontend/scripts/capture-demo.mjs, named <order>-<milliseconds>.png)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

IMAGES = Path(__file__).resolve().parents[1] / "docs" / "images"
FRAMES = IMAGES / "frames"
WIDTH = 960
FRAME_MS = 700
COLORS = 256


def duration(path: Path) -> int:
    """How long a frame is shown: the number after the dash in its name."""
    _, _, ms = path.stem.partition("-")
    return int(ms) if ms.isdigit() else FRAME_MS


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
    # One palette for the whole tour, from every frame, so no page loses its colours.
    # Octree keeps small saturated details (team colours, accents) that median cut drops.
    sheet = Image.new("RGB", (WIDTH, sum(f.height for f in frames)))
    y = 0
    for f in frames:
        sheet.paste(f, (0, y))
        y += f.height
    palette = sheet.quantize(colors=COLORS, method=Image.Quantize.FASTOCTREE)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    target = IMAGES / "demo.gif"
    quantized[0].save(
        target,
        save_all=True,
        append_images=quantized[1:],
        duration=[duration(p) for p in paths],
        loop=0,
        optimize=True,
    )
    shutil.rmtree(FRAMES)
    print(f"wrote {target} ({target.stat().st_size / 1e6:.1f} MB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
