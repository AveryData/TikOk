"""Helpers for persona renderers: ordinals, scripture-style cadence,
ASCII bars, etc. Pure functions, no I/O."""
from __future__ import annotations

from datetime import date

_ORDINAL_WORDS = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
    11: "eleventh", 12: "twelfth",
}

_MONTH_ORDINAL = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
    11: "eleventh", 12: "twelfth",
}


def hour_word(hour_24: int) -> str:
    """0..23 → 'eighth' (am) or 'eighth (evening)' style.

    For the agenda we keep it simple: return the ordinal of the 12-hour
    clock value, with no am/pm marker — the verse format itself implies
    the cadence.
    """
    h12 = hour_24 % 12 or 12
    return _ORDINAL_WORDS.get(h12, f"{h12}th")


def scripture_date(d: date) -> str:
    """E.g. 'the 24th day of the fifth month, in the year 2026'."""
    return (
        f"the {_with_th(d.day)} day of the {_MONTH_ORDINAL[d.month]} month, "
        f"in the year {d.year}"
    )


def _with_th(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return {1: f"{n}st", 2: f"{n}nd", 3: f"{n}rd"}.get(n % 10, f"{n}th")


def ascii_bar(pct: float, width: int = 30, filled: str = "█", empty: str = "░") -> str:
    """Render a horizontal ASCII bar of given width with pct (0..100) filled."""
    pct = max(0.0, min(100.0, pct))
    n_filled = round(pct / 100 * width)
    return filled * n_filled + empty * (width - n_filled)


def time_log(hour: int, minute: int) -> str:
    """24-hour timestamp like '08:30' for terminal-style listings."""
    return f"{hour:02d}:{minute:02d}"


def priority_marker(level: str) -> str:
    """Terminal-style severity markers for the tasks queue."""
    return {
        "Ultra High": "!!!",
        "High": "!!",
        "Medium": "!",
        "Low": ".",
        "None": " ",
    }.get(level, " ")
