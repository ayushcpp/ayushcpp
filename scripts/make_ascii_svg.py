"""Turn a portrait photo into an animated, monochrome ASCII-art SVG.

Run locally (needs Pillow + NumPy), once per photo change:

    python scripts/make_ascii_svg.py path/to/photo.jpg

Output: assets/ascii-portrait.svg. Each row "types" in left to right behind a
block cursor, rows staggered top to bottom; it plays once and then holds.
Set STATIC=1 to emit the finished frame without animation (for previews).

The photo itself is never committed: only the ASCII render is.
"""

import html
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "ascii-portrait.svg"

# Panel geometry (SVG user units == CSS px at the README's width="370").
W, H = 370, 460
BAR = 30                      # title-bar height
PAD_X, PAD_TOP, PAD_BOTTOM = 16, 12, 14
COLS = 84                     # characters per row
CELL_W = (W - 2 * PAD_X) / COLS
CELL_H = CELL_W * 2.0         # monospace cells are ~1:2
ROWS = int((H - BAR - PAD_TOP - PAD_BOTTOM) / CELL_H)

# Sparse -> dense. Dark pixels get dense glyphs; the white backdrop becomes spaces.
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
BG_CUTOFF = 0.90              # brightness above this -> blank (backdrop)

FG = "#c9d1d9"
PANEL = "#0d1117"
BORDER = "#30363d"
CURSOR = "#3fb950"

# Crop box on the 700x900 source: head + shoulders, matching the panel's aspect.
CROP = (30, 105, 670, 870)


def load_luma(path: str) -> np.ndarray:
    img = Image.open(path).convert("L").crop(CROP)
    img = ImageOps.autocontrast(img, cutoff=1)
    # Light unsharp mask so curls, brows and eyes keep their edges once downsampled.
    img = img.filter(ImageFilter.UnsharpMask(radius=3, percent=140, threshold=2))
    small = img.resize((COLS, ROWS), Image.Resampling.BOX)
    return np.asarray(small, dtype=np.float32) / 255.0


def to_rows(luma: np.ndarray) -> list[str]:
    rows = []
    n = len(RAMP) - 1
    for line in luma:
        chars = []
        for v in line:
            if v >= BG_CUTOFF:
                chars.append(" ")
            else:
                # Stretch the subject's tonal range across the whole ramp.
                t = 1.0 - (v / BG_CUTOFF)
                chars.append(RAMP[max(1, min(n, round(t ** 0.85 * n)))])
        rows.append("".join(chars))
    return rows


def window_chrome(title: str) -> str:
    return f"""
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{PANEL}" stroke="{BORDER}"/>
  <path d="M0.5 {BAR} H{W-0.5}" stroke="{BORDER}"/>
  <circle cx="18" cy="15" r="5" fill="#ff5f56"/>
  <circle cx="34" cy="15" r="5" fill="#ffbd2e"/>
  <circle cx="50" cy="15" r="5" fill="#27c93f"/>
  <text x="{W/2}" y="19.5" text-anchor="middle" class="title">{html.escape(title)}</text>"""


def build_svg(rows: list[str], static: bool) -> str:
    x0 = PAD_X
    y0 = BAR + PAD_TOP
    width = COLS * CELL_W
    font = CELL_H * 0.92
    row_dur, stagger, start = 0.38, 0.045, 0.25

    parts = []
    for i, row in enumerate(rows):
        top = y0 + i * CELL_H
        base = top + CELL_H * 0.78
        if not row.strip():
            continue
        parts.append(
            f'<text x="{x0}" y="{base:.2f}" xml:space="preserve" textLength="{width:.2f}" '
            f'lengthAdjust="spacingAndGlyphs">{html.escape(row)}</text>'
        )
        if static:
            continue
        d = start + i * stagger
        # A panel-coloured cover shrinks toward the right edge, revealing the row,
        # while a block cursor rides its left edge and then disappears.
        parts.append(
            f'<rect class="cover" x="{x0-1}" y="{top-0.6:.2f}" width="{width+2:.2f}" '
            f'height="{CELL_H+1.2:.2f}" style="animation-delay:{d:.3f}s"/>'
        )
        parts.append(
            f'<rect class="cur" x="{x0}" y="{top+0.6:.2f}" width="{CELL_W:.2f}" '
            f'height="{CELL_H-1.2:.2f}" style="animation-delay:{d:.3f}s"/>'
        )

    anim_css = "" if static else f"""
    .cover {{ fill: {PANEL}; transform-box: fill-box; transform-origin: right center;
             animation: wipe {row_dur}s linear both; }}
    .cur {{ fill: {CURSOR}; opacity: 0; animation: cur {row_dur}s linear both; }}
    @keyframes wipe {{ from {{ transform: scaleX(1); }} to {{ transform: scaleX(0); }} }}
    @keyframes cur {{
      0%   {{ opacity: 0; transform: translateX(0); }}
      1%   {{ opacity: 1; }}
      99%  {{ opacity: 1; transform: translateX({width-CELL_W:.2f}px); }}
      100% {{ opacity: 0; transform: translateX({width-CELL_W:.2f}px); }}
    }}"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t" xml:space="preserve">
  <title id="t">ASCII portrait of Ayush</title>
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace; }}
    .title {{ font-size: 11.5px; fill: #8b949e; }}
    .art text {{ font-size: {font:.2f}px; fill: {FG}; white-space: pre; }}{anim_css}
  </style>{window_chrome("~/portrait.txt")}
  <g class="art">
    {chr(10).join("    " + p for p in parts).lstrip()}
  </g>
</svg>
"""


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/make_ascii_svg.py path/to/photo.jpg")
    rows = to_rows(load_luma(sys.argv[1]))
    static = os.environ.get("STATIC") == "1"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = OUT.with_name("ascii-portrait.static.svg") if static else OUT
    out.write_text(build_svg(rows, static), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}  ({COLS}x{ROWS} chars)")


if __name__ == "__main__":
    main()
