"""Fetch the public contribution calendar and write data/contributions.json.

    python scripts/fetch_contributions.py [username]

Uses https://github.com/users/<user>/contributions, the HTML fragment GitHub's
own profile page loads. No token, no third-party service, standard library only.
That fragment is undocumented, so if GitHub changes its markup this script
fails loudly instead of writing an empty graph.
"""

import datetime as dt
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "contributions.json"
DEFAULT_USER = "ayushcpp"

COUNT_RE = re.compile(r"^\s*(No|[\d,]+)\s+contributions?\b", re.I)


class CalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cells: dict[str, dict] = {}       # td id -> {date, level}
        self.tips: dict[str, str] = {}         # td id -> tooltip text
        self._tip_for: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and "ContributionCalendar-day" in (a.get("class") or "") and a.get("data-date"):
            self.cells[a["id"]] = {"date": a["data-date"], "level": int(a.get("data-level", 0))}
        elif tag == "tool-tip" and a.get("for"):
            self._tip_for, self._buf = a["for"], []

    def handle_data(self, data):
        if self._tip_for:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self._tip_for:
            self.tips[self._tip_for] = "".join(self._buf).strip()
            self._tip_for = None


def fetch(user: str) -> str:
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "profile-readme-heatmap"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def streaks(days: list[dict], today: dt.date) -> tuple[int, int]:
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    # Current streak: ending today, or yesterday if today has no contributions yet.
    by_date = {d["date"]: d["count"] for d in days}
    day = today if by_date.get(today.isoformat(), 0) > 0 else today - dt.timedelta(days=1)
    current = 0
    while by_date.get(day.isoformat(), 0) > 0:
        current += 1
        day -= dt.timedelta(days=1)
    return current, longest


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USER
    p = CalendarParser()
    p.feed(fetch(user))

    days = []
    for cid, cell in p.cells.items():
        m = COUNT_RE.match(p.tips.get(cid, ""))
        if not m:
            sys.exit(f"could not read a count for {cell['date']}: markup changed?")
        n = 0 if m.group(1).lower() == "no" else int(m.group(1).replace(",", ""))
        days.append({**cell, "count": n})
    days.sort(key=lambda d: d["date"])
    if len(days) < 300:
        sys.exit(f"only parsed {len(days)} days: markup changed?")

    today = dt.date.fromisoformat(days[-1]["date"])
    current, longest = streaks(days, today)
    best = max(days, key=lambda d: d["count"])
    months: dict[str, int] = {}
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["count"]

    data = {
        "user": user,
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "total": sum(d["count"] for d in days),
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]},
        "active_days": sum(1 for d in days if d["count"] > 0),
        "months": months,
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"{user}: {data['total']} contributions over {len(days)} days, "
          f"streak {current} (longest {longest}) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
