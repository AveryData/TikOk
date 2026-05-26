"""Google Calendar source. Pulls today's events (single-day) and an
'upcoming this week' list (next 7 days, excluding today).

Authentication: OAuth installed-app flow with a stored refresh token.
Set these env vars:
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN

Run scripts/google_oauth_setup.py locally once to obtain the refresh token.

Multiple calendars are supported: set GOOGLE_CALENDAR_IDS to a comma-
separated list of calendar IDs. Default is just the primary.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.models import CalendarEvent, UpcomingEvent

logger = logging.getLogger("briefing.calendar")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def _mint_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange the long-lived refresh token for a short-lived access token."""
    with httpx.Client(timeout=10) as c:
        resp = c.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _parse_event_time(when: dict[str, Any], tz: ZoneInfo) -> tuple[datetime | None, bool]:
    """Return (datetime in `tz`, is_all_day). when is the Google event's
    start or end block."""
    if "dateTime" in when:
        dt = datetime.fromisoformat(when["dateTime"].replace("Z", "+00:00"))
        return dt.astimezone(tz), False
    if "date" in when:
        d = date.fromisoformat(when["date"])
        return datetime.combine(d, time(0, 0), tzinfo=tz), True
    return None, False


def _fetch_calendar(
    access_token: str,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
) -> list[dict[str, Any]]:
    """Fetch events for a single calendar in the given window. Expands
    recurring events into instances."""
    encoded_id = httpx.QueryParams({"id": calendar_id}).get("id")
    # Just use the calendar_id directly in the URL; httpx will quote it.
    url = f"{CALENDAR_API}/calendars/{calendar_id}/events"
    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",  # expand recurring
        "orderBy": "startTime",
        "maxResults": "100",
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=15) as c:
        resp = c.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get("items", [])


def fetch_today_and_upcoming(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    today: date,
    tz_name: str,
    calendar_ids: list[str],
    upcoming_limit: int = 15,
    upcoming_include_recurring: bool = True,
) -> tuple[list[CalendarEvent], list[UpcomingEvent]]:
    """Returns (today_events, upcoming_events).

    today_events: everything scheduled for `today` across all calendars
        (including recurring routine events).
    upcoming_events: next 7 days (excluding today). Includes recurring
        events by default — set upcoming_include_recurring=False to drop
        them (was the default, but reverted because Avery's calendar is
        mostly recurring blocks and the filter wiped whole days).
    """
    tz = ZoneInfo(tz_name)
    start_of_today = datetime.combine(today, time(0, 0), tzinfo=tz)
    end_of_today = start_of_today + timedelta(days=1)
    end_of_week = start_of_today + timedelta(days=8)  # today + 7 more

    access_token = _mint_access_token(client_id, client_secret, refresh_token)

    today_events: list[CalendarEvent] = []
    upcoming: list[UpcomingEvent] = []

    for cal_id in calendar_ids:
        try:
            items = _fetch_calendar(access_token, cal_id, start_of_today, end_of_week)
        except Exception as exc:  # noqa: BLE001
            logger.warning("calendar fetch failed for %s: %s", cal_id, exc)
            continue

        for item in items:
            # Skip cancelled / transparent (= free time markers) for clarity.
            if item.get("status") == "cancelled":
                continue
            if item.get("transparency") == "transparent":
                continue

            start_dt, all_day = _parse_event_time(item.get("start", {}), tz)
            end_dt, _ = _parse_event_time(item.get("end", {}), tz)
            if start_dt is None:
                continue

            title = item.get("summary", "(no title)").strip()
            location = item.get("location") or item.get("conferenceUrl")
            if location and location.startswith("http"):
                # Trim long Notion/Meet URLs to just the host for display.
                location = "Zoom" if "zoom" in location else (
                    "Meet" if "meet.google" in location else None
                )

            if start_dt < end_of_today:
                today_events.append(CalendarEvent(
                    title=title,
                    start=start_dt,
                    end=end_dt,
                    all_day=all_day,
                    location=location,
                ))
            else:
                # Skip recurring events for the upcoming-week digest —
                # daily routine items like "Email" or "Prep Kids For Day"
                # otherwise drown out the one-off events worth knowing about.
                if not upcoming_include_recurring and item.get("recurringEventId"):
                    continue
                upcoming.append(UpcomingEvent(
                    title=title,
                    when=start_dt,
                    location=location,
                ))

    today_events.sort(key=lambda e: (not e.all_day, e.start or start_of_today))
    upcoming.sort(key=lambda u: u.when)

    # Deduplicate upcoming by exact title (case-insensitive). Avery's calendar
    # has many routines that recur daily (Prep Kids For Day, Starting Work
    # Day, Email, etc.). Showing each one Mon-Fri bloats the section and
    # pushes the layout off one page. First occurrence wins so the earliest
    # instance of each recurring event still shows up.
    seen: set[str] = set()
    deduped: list[UpcomingEvent] = []
    duplicates_dropped = 0
    for u in upcoming:
        key = u.title.strip().lower()
        if key in seen:
            duplicates_dropped += 1
            continue
        seen.add(key)
        deduped.append(u)
    upcoming = deduped[:upcoming_limit]

    logger.info(
        "calendar: %d events today, %d upcoming (across %d cal(s), cap=%d, deduped=%d)",
        len(today_events), len(upcoming), len(calendar_ids), upcoming_limit, duplicates_dropped,
    )
    return today_events, upcoming
