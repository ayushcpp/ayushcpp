"""Render data/contributions.json into assets/contrib-heatmap.svg.

    python scripts/render_heatmap_svg.py

Cells slide in once along the diagonal, then hold. STATIC=1 writes a frozen
frame (assets/contrib-heatmap.static.svg) for previews. Standard library only.
"""

import datetime as dt
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "assets" / "contrib-heatmap.svg"

W = 860
BAR = 30
CELL, GAP = 12, 3
STEP = CELL + GAP
GRID_X, GRID_Y = 52, BAR + 40
PANEL, BORDER = "#0d1117", "#30363d"
FG, MUTED = "#c9d1d9", "#8b949e"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
BEST = "#69f0a0"


def fmt_day(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def build_svg(data: dict, static: bool) -> str:
    days = data["days"]
    first = dt.date.fromisoformat(days[0]["date"])
    # GitHub's calendar columns start on Sunday.
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    weeks = (dt.date.fromisoformat(days[-1]["date"]) - start).days // 7 + 1
    best_count = data["best_day"]["count"]

    cells, month_labels = [], []
    seen_month = None
    for d in days:
        date = dt.date.fromisoformat(d["date"])
        offset = (date - start).days
        wk, dow = offset // 7, offset % 7
        x, y = GRID_X + wk * STEP, GRID_Y + dow * STEP
        fill = BEST if best_count and d["count"] == best_count else LEVELS[min(d["level"], 4)]
        tip = f'{d["count"]} contribution{"s" if d["count"] != 1 else ""} on {fmt_day(d["date"])}'
        style = "" if static else f' style="animation-delay:{(wk + dow) * 0.014:.3f}s"'
        cells.append(f'<rect class="c" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                     f'fill="{fill}"{style}><title>{tip}</title></rect>')
        if date.day <= 7 and dow == 0 and (date.year, date.month) != seen_month and wk < weeks - 2:
            seen_month = (date.year, date.month)
            month_labels.append(f'<text x="{x}" y="{GRID_Y - 9}" class="lbl">{date.strftime("%b")}</text>')

    day_labels = "".join(
        f'<text x="{GRID_X - 10}" y="{GRID_Y + i * STEP + 10}" class="lbl" text-anchor="end">{name}</text>'
        for i, name in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )

    grid_bottom = GRID_Y + 7 * STEP
    foot_y = grid_bottom + 30
    H = foot_y + 36

    legend_x = GRID_X + weeks * STEP - (5 * STEP + 70)
    legend = (f'<text x="{legend_x}" y="{foot_y}" class="lbl">Less</text>'
              + "".join(f'<rect x="{legend_x + 34 + i * STEP}" y="{foot_y - 10}" width="{CELL}" '
                        f'height="{CELL}" rx="2.5" fill="{c}"/>' for i, c in enumerate(LEVELS))
              + f'<text x="{legend_x + 34 + 5 * STEP + 4}" y="{foot_y}" class="lbl">More</text>')

    total = f'{data["total"]:,}'
    stats = (f'<tspan fill="#39d353" font-weight="700">{total}</tspan> contributions in the last year'
             f'<tspan fill="{MUTED}">  ·  </tspan>streak <tspan fill="#39d353" font-weight="700">'
             f'{data["current_streak"]}</tspan>d'
             f'<tspan fill="{MUTED}">  ·  </tspan>longest <tspan fill="#39d353" font-weight="700">'
             f'{data["longest_streak"]}</tspan>d'
             f'<tspan fill="{MUTED}">  ·  </tspan>best <tspan fill="{BEST}" font-weight="700">'
             f'{data["best_day"]["count"]}</tspan> on {fmt_day(data["best_day"]["date"])}')

    anim_css = "" if static else """
    .c { animation: pop .45s cubic-bezier(.2,.8,.3,1.2) both; transform-box: fill-box; transform-origin: center; }
    @keyframes pop { from { opacity: 0; transform: translate(-6px, -6px) scale(.4); } to { opacity: 1; transform: none; } }"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
  <title id="t">{html.escape(data["user"])}: {total} contributions in the last year (updated {data["updated"]})</title>
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace; }}
    .title {{ font-size: 11.5px; fill: {MUTED}; }}
    .lbl {{ font-size: 10.5px; fill: {MUTED}; }}
    .stat {{ font-size: 12px; fill: {FG}; }}{anim_css}
  </style>
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{PANEL}" stroke="{BORDER}"/>
  <path d="M0.5 {BAR} H{W-0.5}" stroke="{BORDER}"/>
  <circle cx="18" cy="15" r="5" fill="#ff5f56"/>
  <circle cx="34" cy="15" r="5" fill="#ffbd2e"/>
  <circle cx="50" cy="15" r="5" fill="#27c93f"/>
  <text x="{W/2}" y="19.5" text-anchor="middle" class="title">~/contributions.sh · updated {data["updated"]}</text>
  {"".join(month_labels)}
  {day_labels}
  <g>
    {chr(10).join("    " + c for c in cells).lstrip()}
  </g>
  <text x="{GRID_X}" y="{foot_y}" class="stat">{stats}</text>
  {legend}
</svg>
"""


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    static = os.environ.get("STATIC") == "1"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = OUT.with_name("contrib-heatmap.static.svg") if static else OUT
    out.write_text(build_svg(data, static), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
