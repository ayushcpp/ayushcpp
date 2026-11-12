"""Turn a portrait photo into an animated, shaded ASCII-art SVG.

Run locally (needs Pillow + NumPy), once per photo change:

    python scripts/make_ascii_svg.py path/to/photo.jpg [out.svg]

Output: assets/ascii-portrait.svg. Each row "types" in left to right behind a
block cursor, rows staggered top to bottom; it plays once and then holds.
Set STATIC=1 to emit the finished frame without animation (for previews).

How it stays legible at 420 px wide:
  * the white backdrop is cut out by flood-filling from the borders, so only
    the subject is drawn;
  * tones are histogram-equalised over the subject only, so skin, brows, eyes
    and lips spread across the glyph ramp instead of all landing on the densest
    glyphs (the dark hair and shirt would otherwise eat most of the range);
  * local contrast is boosted only gently and over a wide radius: a tight boost
    turned soft shading, like the side of the nose, into hard stripes;
  * every glyph is also shaded (12 grey levels), so tone is carried by both the
    character's density and its brightness;
  * very dark areas (hair, shirt) keep a floor so their silhouette still shows.

The photo itself is never committed: only the ASCII render is.
"""

import html
import os
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "ascii-portrait.svg"

# Panel geometry (SVG user units == CSS px at the README's width="420").
W, H = 420, 460
BAR = 30                      # title-bar height
PAD_X, PAD_TOP, PAD_BOTTOM = 16, 10, 12
COLS = int(os.environ.get("COLS", 120))
CELL_W = (W - 2 * PAD_X) / COLS
CELL_H = CELL_W * 2.0         # monospace cells are ~1:2
ROWS = int((H - BAR - PAD_TOP - PAD_BOTTOM) / CELL_H)

# Sparse -> dense, chosen so each step is visibly denser than the last.
RAMP = os.environ.get("RAMP", " .`:-=+*ox%#&8@")
MODE = os.environ.get("MODE", "positive")   # positive: bright = dense; negative: dark = dense
FLOOR = float(os.environ.get("FLOOR", 0.14))  # minimum tone for subject cells
GAMMA = float(os.environ.get("GAMMA", 1.35))   # >1 darkens midtones (features pop)
DETAIL = float(os.environ.get("DETAIL", 0.25))  # local contrast boost
BG_LUMA = 0.93                # brighter than this and connected to the border = backdrop

NSHADES = int(os.environ.get("NSHADES", 12))  # grey levels for glyph fill
DARK, LIGHT = (0x3a, 0x41, 0x4a), (0xf6, 0xf8, 0xfa)
SHADES = ["#%02x%02x%02x" % tuple(round(a + (b - a) * i / (NSHADES - 1)) for a, b in zip(DARK, LIGHT))
          for i in range(NSHADES)]
EQ = float(os.environ.get("EQ", 0.8))           # 0 = linear stretch, 1 = full histogram equalisation
BLUR = float(os.environ.get("BLUR", 7))     # neighbourhood size for the detail boost (cells)
USM_RADIUS = float(os.environ.get("USM_RADIUS", 2))      # pre-sharpen on the full-res photo
USM_PERCENT = int(os.environ.get("USM_PERCENT", 80))
PANEL = "#0d1117"
BORDER = "#30363d"
CURSOR = "#3fb950"

# Crop on the 700x900 source: hair to collar, centred on the face, at the art area's aspect.
CROP_TOP, CROP_BOTTOM, CENTER_X = 128, 742, 341
_half = (W - 2 * PAD_X) / (ROWS * CELL_H) * (CROP_BOTTOM - CROP_TOP) / 2
CROP = (round(CENTER_X - _half), CROP_TOP, round(CENTER_X + _half), CROP_BOTTOM)


def load(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (tone 0..1, subject mask) at COLS x ROWS."""
    img = Image.open(path).convert("L").crop(CROP)
    raw = np.asarray(img.resize((COLS, ROWS), Image.Resampling.BOX), dtype=np.float32) / 255.0

    # Backdrop = near-white cells reachable from the border.
    bg = np.zeros_like(raw, dtype=bool)
    q = deque((r, c) for r in range(ROWS) for c in (0, COLS - 1))
    q.extend((r, c) for c in range(COLS) for r in (0, ROWS - 1))
    while q:
        r, c = q.popleft()
        if 0 <= r < ROWS and 0 <= c < COLS and not bg[r, c] and raw[r, c] > BG_LUMA:
            bg[r, c] = True
            q.extend(((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)))
    subject = ~bg

    # Local detail: unsharp the full-res crop, then resample.
    sharp = img.filter(ImageFilter.UnsharpMask(radius=USM_RADIUS, percent=USM_PERCENT, threshold=2))
    tone = np.asarray(sharp.resize((COLS, ROWS), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0

    # Stretch contrast over the subject only (the white backdrop would flatten it).
    lo, hi = np.percentile(tone[subject], [3, 99])
    linear = np.clip((tone - lo) / max(hi - lo, 1e-6), 0, 1)

    # Histogram-equalise over the subject: the dark hair and shirt fill most of
    # the tonal range, which otherwise squeezes all skin into the top glyphs.
    vals = np.sort(tone[subject])
    equalised = np.searchsorted(vals, tone, side="right") / len(vals)
    tone = (1 - EQ) * linear + EQ * equalised

    # Grid-level detail boost: push each cell away from its neighbourhood mean,
    # which separates eyes, brows and lips from the skin around them.
    if DETAIL > 0:
        blur = Image.fromarray((tone * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(BLUR))
        local = np.asarray(blur, dtype=np.float32) / 255.0
        tone = np.clip(tone + DETAIL * (tone - local), 0, 1)
    return tone, subject


def to_cells(tone: np.ndarray, subject: np.ndarray) -> list[list[tuple[str, int]]]:
    """Each cell -> (glyph, shade index). Blank cells get shade -1."""
    n = len(RAMP) - 1
    rows = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            if not subject[r, c]:
                row.append((" ", -1))
                continue
            v = float(tone[r, c])
            if MODE == "negative":
                v = 1.0 - v
            t = FLOOR + (1 - FLOOR) * v ** GAMMA
            g = RAMP[max(1, min(n, round(t * n)))]
            s = max(0, min(len(SHADES) - 1, int(t * len(SHADES))))
            row.append((g, s))
        rows.append(row)
    return rows


def row_markup(row: list[tuple[str, int]]) -> str:
    """Group runs of equal shade into tspans to keep the file small."""
    out, run, cur = [], [], None
    for g, s in row + [("", -2)]:
        key = None if g == " " else s
        if key != cur and run:
            text = html.escape("".join(run))
            out.append(text if cur is None else f'<tspan class="s{cur}">{text}</tspan>')
            run = []
        cur = key
        run.append(g)
    return "".join(out)


def window_chrome(title: str) -> str:
    return f"""
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{PANEL}" stroke="{BORDER}"/>
  <path d="M0.5 {BAR} H{W-0.5}" stroke="{BORDER}"/>
  <circle cx="18" cy="15" r="5" fill="#ff5f56"/>
  <circle cx="34" cy="15" r="5" fill="#ffbd2e"/>
  <circle cx="50" cy="15" r="5" fill="#27c93f"/>
  <text x="{W/2}" y="19.5" text-anchor="middle" class="title">{html.escape(title)}</text>"""


def build_svg(rows: list[list[tuple[str, int]]], static: bool) -> str:
    x0 = PAD_X
    y0 = BAR + PAD_TOP
    width = COLS * CELL_W
    font = CELL_H * 0.92
    row_dur, stagger, start = 0.38, 0.04, 0.25

    parts = []
    for i, row in enumerate(rows):
        if all(g == " " for g, _ in row):
            continue
        top = y0 + i * CELL_H
        base = top + CELL_H * 0.78
        parts.append(
            f'<text x="{x0}" y="{base:.2f}" xml:space="preserve" textLength="{width:.2f}" '
            f'lengthAdjust="spacingAndGlyphs">{row_markup(row)}</text>'
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
            f'<rect class="cur" x="{x0}" y="{top+0.6:.2f}" width="{CELL_W*1.4:.2f}" '
            f'height="{CELL_H-1.2:.2f}" style="animation-delay:{d:.3f}s"/>'
        )

    shade_css = " ".join(f".s{i}{{fill:{c}}}" for i, c in enumerate(SHADES))
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
    .art text {{ font-size: {font:.2f}px; font-weight: 700; white-space: pre; }}
    {shade_css}{anim_css}
  </style>{window_chrome("~/portrait.txt")}
  <g class="art">
    {chr(10).join("    " + p for p in parts).lstrip()}
  </g>
</svg>
"""


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python scripts/make_ascii_svg.py path/to/photo.jpg [out.svg]")
    tone, subject = load(sys.argv[1])
    rows = to_cells(tone, subject)
    static = os.environ.get("STATIC") == "1"
    if len(sys.argv) == 3:
        out = Path(sys.argv[2])
    else:
        out = OUT.with_name("ascii-portrait.static.svg") if static else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_svg(rows, static), encoding="utf-8")
    print(f"wrote {out}  ({COLS}x{ROWS} chars, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
