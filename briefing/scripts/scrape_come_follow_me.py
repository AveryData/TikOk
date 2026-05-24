"""Scrape the official 2026 OT Come Follow Me manual into a JSON file.

Run this once locally (the Cloud Run container's egress policy may block
the LDS domain). Output replaces app/data/come_follow_me_2026.json.

Usage:
    cd briefing
    pip install httpx beautifulsoup4 lxml
    python scripts/scrape_come_follow_me.py

The manual's TOC links each weekly lesson page. Each lesson page header
has the date range and scripture reference. We extract:
    - week.start, week.end (Mon-Sun)
    - week.reference  (e.g. "Genesis 12-17; Abraham 1-2")
    - week.theme      (lesson title)
    - week.url        (canonical URL of that week's lesson page)

Daily readings, if you want them, can be added manually to each
week.daily map (keyed by ISO date). The manual itself is organized
weekly — daily breakdowns come from third-party reading plans, not the
official manual.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    print("Install deps first: pip install httpx beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(1)


BASE = "https://www.churchofjesuschrist.org"
TOC_URL = (
    f"{BASE}/study/manual/come-follow-me-for-home-and-church-old-testament-2026?lang=eng"
)
OUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "come_follow_me_2026.json"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Examples that should match:
#   "December 29-January 4. Genesis 1-2; Moses 2-3"
#   "January 5-11. Genesis 3-4; Moses 4-5"
DATE_REF_RE = re.compile(
    r"^\s*(?P<start_month>[A-Z][a-z]+)\s+(?P<start_day>\d{1,2})"
    r"\s*[–-]\s*"
    r"(?:(?P<end_month>[A-Z][a-z]+)\s+)?(?P<end_day>\d{1,2})"
    r"\s*[.·:]\s*"
    r"(?P<ref>.+?)\s*$",
    re.DOTALL,
)

MONTHS = {
    m: i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"],
        start=1,
    )
}


def _parse_week_label(label: str, year_hint: int = 2026) -> tuple[date, date, str] | None:
    """Parse 'December 29-January 4. Genesis 1-2; Moses 2-3' → (start, end, ref)."""
    m = DATE_REF_RE.match(label)
    if not m:
        return None
    start_month = MONTHS[m.group("start_month")]
    start_day = int(m.group("start_day"))
    end_month_name = m.group("end_month") or m.group("start_month")
    end_month = MONTHS[end_month_name]
    end_day = int(m.group("end_day"))

    # Year inference: if start_month=12 and end_month=1, the start is the
    # prior year. (The 2026 OT manual's intro week is Dec 29 2025 - Jan 4 2026.)
    start_year = year_hint - 1 if start_month == 12 and end_month == 1 else year_hint
    end_year = year_hint

    return (
        date(start_year, start_month, start_day),
        date(end_year, end_month, end_day),
        m.group("ref").strip(),
    )


def main() -> None:
    with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as client:
        print(f"Fetching {TOC_URL}")
        toc_html = client.get(TOC_URL).raise_for_status().text

        soup = BeautifulSoup(toc_html, "lxml")
        weeks: list[dict] = []

        # Each weekly lesson is linked in the TOC. The Church site renders
        # the TOC as a list of anchors; lesson hrefs match the manual path.
        seen = set()
        for a in soup.select("a[href*='/study/manual/come-follow-me-for-home-and-church-old-testament-2026/']"):
            href = a["href"].split("?")[0]
            if href in seen:
                continue
            seen.add(href)

            text = " ".join(a.get_text(" ", strip=True).split())
            parsed = _parse_week_label(text)
            if not parsed:
                continue
            start, end, reference = parsed

            # Fetch lesson page to get the lesson title/theme.
            lesson_url = href if href.startswith("http") else BASE + href
            print(f"  · {start} → {reference[:60]}")
            theme = None
            try:
                lesson_soup = BeautifulSoup(
                    client.get(lesson_url).raise_for_status().text, "lxml"
                )
                # The lesson title is typically in <h1> with class title-related.
                h1 = lesson_soup.find("h1")
                if h1:
                    theme = " ".join(h1.get_text(" ", strip=True).split())
            except Exception as exc:
                print(f"    (could not fetch lesson title: {exc})")

            weeks.append({
                "start": start.isoformat(),
                "end": end.isoformat(),
                "reference": reference,
                "theme": theme,
                "url": lesson_url,
                "daily": {},
            })

    weeks.sort(key=lambda w: w["start"])
    out = {
        "_README": (
            "Generated by scripts/scrape_come_follow_me.py from the official 2026 "
            "OT manual TOC. To populate 'daily' readings, add entries to each week "
            "(keyed by ISO date) sourced from your preferred reading plan."
        ),
        "weeks": weeks,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"Wrote {len(weeks)} weeks to {OUT_PATH}")


if __name__ == "__main__":
    main()
