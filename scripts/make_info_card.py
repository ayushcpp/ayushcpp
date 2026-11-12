"""Render the neofetch-style info card: assets/info-card.svg.

Edit the INFO list below, then run:

    python scripts/make_info_card.py

Lines fade and slide in one after another, once. STATIC=1 writes a frozen
frame (assets/info-card.static.svg) for previews.
"""

import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "info-card.svg"

W, H = 490, 460               # same height as the portrait so the table row lines up
BAR = 30
PANEL, BORDER = "#0d1117", "#30363d"
FG, MUTED = "#c9d1d9", "#8b949e"
KEY_COLORS = ["#7ee787", "#79c0ff", "#d2a8ff", "#ffa657", "#ff7b72", "#a5d6ff"]

USER, HOST = "ayush", "github"

# (key, value). A key of "" continues the previous entry on a new line.
# Keep values under ~44 characters so they fit at this width.
INFO = [
    ("Name", "Ayush Gairola"),
    ("Role", "ML engineer in the making"),
    ("Study", "Student @ Graphic Era, India"),
    ("Focus", "Computer Vision · NLP · LLM apps"),
    ("Now", "semantic search with embeddings + vector DBs"),
    ("Langs", "Python · C++ · JavaScript · TypeScript"),
    ("ML", "OpenCV · MediaPipe · scikit-learn · pandas"),
    ("", "LangChain · ChromaDB · sentence-transformers"),
    ("Apps", "Gradio · Streamlit · three.js · Vite · Vercel"),
    ("Grind", "DSA in C++ · 50+ LeetCode / GfG problems"),
    ("OS", "Fedora Linux · zsh · kitty"),
]

PALETTE = ["#484f58", "#ff7b72", "#7ee787", "#d29922", "#79c0ff", "#d2a8ff", "#a5d6ff", "#e6edf3"]


def window_chrome(title: str) -> str:
    return f"""
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{PANEL}" stroke="{BORDER}"/>
  <path d="M0.5 {BAR} H{W-0.5}" stroke="{BORDER}"/>
  <circle cx="18" cy="15" r="5" fill="#ff5f56"/>
  <circle cx="34" cy="15" r="5" fill="#ffbd2e"/>
  <circle cx="50" cy="15" r="5" fill="#27c93f"/>
  <text x="{W/2}" y="19.5" text-anchor="middle" class="title">{html.escape(title)}</text>"""


def build_svg(static: bool) -> str:
    x, key_w = 24, 62
    y = BAR + 34
    lh = 25
    lines = []
    delay, step = 0.35, 0.11

    def line(content: str) -> None:
        nonlocal delay
        style = "" if static else f' style="animation-delay:{delay:.2f}s"'
        lines.append(f'<g class="ln"{style}>{content}</g>')
        delay += step

    # prompt + header
    line(f'<text x="{x}" y="{y}" class="prompt"><tspan fill="#7ee787">{USER}@{HOST}</tspan>'
         f'<tspan fill="{MUTED}"> ~ $ </tspan><tspan fill="{FG}">neofetch</tspan></text>')
    y += lh + 4
    line(f'<text x="{x}" y="{y}" class="hdr"><tspan fill="#7ee787">{USER}</tspan>'
         f'<tspan fill="{FG}">@</tspan><tspan fill="#79c0ff">{HOST}</tspan></text>')
    y += 10
    line(f'<path d="M{x} {y} h{12*8.4:.0f}" stroke="{MUTED}" stroke-width="1.2" stroke-dasharray="5 3"/>')
    y += lh - 2

    color_i = -1
    for key, val in INFO:
        if key:
            color_i += 1
        color = KEY_COLORS[color_i % len(KEY_COLORS)]
        k = (f'<tspan fill="{color}" font-weight="700">{html.escape(key)}</tspan>' if key else "")
        line(f'<text x="{x}" y="{y}" class="kv">{k}</text>'
             f'<text x="{x+key_w}" y="{y}" class="kv" fill="{FG}">{html.escape(val)}</text>')
        y += lh

    y += 4
    blocks = "".join(
        f'<rect x="{x + i*26}" y="{y-12}" width="22" height="14" rx="2" fill="{c}"/>'
        for i, c in enumerate(PALETTE)
    )
    line(blocks)
    y += lh
    cursor_cls = "" if static else ' class="blink"'
    line(f'<text x="{x}" y="{y}" class="prompt"><tspan fill="#7ee787">{USER}@{HOST}</tspan>'
         f'<tspan fill="{MUTED}"> ~ $ </tspan></text>'
         f'<rect{cursor_cls} x="{x + 15*7.9:.1f}" y="{y-12}" width="8" height="15" fill="#3fb950"/>')

    anim_css = "" if static else """
    .ln { animation: in .5s cubic-bezier(.2,.7,.3,1) both; }
    @keyframes in { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: none; } }
    .blink { animation: blink 1.1s steps(1) infinite; }
    @keyframes blink { 50% { opacity: 0; } }"""

    body = "\n    ".join(lines)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">neofetch: ayush@github</title>
  <desc id="d">{html.escape("; ".join(f"{k}: {v}" if k else v for k, v in INFO))}</desc>
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace; }}
    .title {{ font-size: 11.5px; fill: {MUTED}; }}
    .prompt {{ font-size: 13px; }}
    .hdr {{ font-size: 15px; font-weight: 700; }}
    .kv {{ font-size: 12.5px; }}{anim_css}
  </style>{window_chrome("ayush@github: ~")}
  <g>
    {body}
  </g>
</svg>
"""


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = OUT.with_name("info-card.static.svg") if static else OUT
    out.write_text(build_svg(static), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
