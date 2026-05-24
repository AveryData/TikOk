"""Static daily extras: joke of the day, quote of the day, Come Follow Me."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.models import ComeFollowMe, Quote, YearProgress

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def _jokes() -> list[str]:
    return json.loads((DATA_DIR / "jokes.json").read_text())


@lru_cache
def _quotes_raw() -> list[dict]:
    return json.loads((DATA_DIR / "quotes.json").read_text())


@lru_cache
def _cfm_raw() -> dict:
    return json.loads((DATA_DIR / "come_follow_me_2026.json").read_text())


def joke_for(d: date) -> str:
    jokes = _jokes()
    return jokes[d.toordinal() % len(jokes)]


def quote_for(d: date) -> Quote:
    raw = _quotes_raw()
    item = raw[d.toordinal() % len(raw)]
    return Quote(text=item["text"], attribution=item.get("attribution"))


def year_progress_for(d: date) -> YearProgress:
    start = date(d.year, 1, 1)
    end = date(d.year, 12, 31)
    return YearProgress(
        day_of_year=(d - start).days + 1,
        days_in_year=(end - start).days + 1,
    )


def come_follow_me_for(d: date) -> ComeFollowMe | None:
    iso = d.isoformat()
    for week in _cfm_raw().get("weeks", []):
        if week["start"] <= iso <= week["end"]:
            start_d = date.fromisoformat(week["start"])
            end_d = date.fromisoformat(week["end"])
            label = (
                f"{start_d.strftime('%b %-d')}–{end_d.strftime('%-d')}"
                if start_d.month == end_d.month
                else f"{start_d.strftime('%b %-d')}–{end_d.strftime('%b %-d')}"
            )
            return ComeFollowMe(
                week_label=label,
                week_reference=week["reference"],
                week_theme=week.get("theme"),
                today_reference=(week.get("daily") or {}).get(iso),
            )
    return None
