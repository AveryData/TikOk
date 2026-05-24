"""Google Calendar source. Stub for now — wire up after style is chosen."""
from __future__ import annotations

from datetime import date

from app.models import CalendarEvent


def fetch_today_events(for_date: date, calendar_id: str = "primary") -> list[CalendarEvent]:
    """Fetch events from the user's Google Calendar for the given date.

    Implementation will use google-api-python-client with stored OAuth creds.
    Returns events sorted by start time, with all-day events first.
    """
    raise NotImplementedError(
        "Google Calendar source not yet wired. "
        "See README for OAuth setup."
    )
