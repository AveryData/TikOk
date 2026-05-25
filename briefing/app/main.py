from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.models import Briefing, Countdown, TickerQuote, Weather
from app.render.pdf import render_html, render_pdf
from app.render.sample import sample_briefing
from app.sources.calendar import fetch_today_and_upcoming
from app.sources.extras import prayer_group_for
from app.sources.tasks import fetch_top_tasks
from app.sources.ticker import fetch_ticker
from app.sources.weather import fetch_weather

logger = logging.getLogger("briefing")
logger.setLevel(logging.INFO)

app = FastAPI(title="A Record of Our Day", version="0.3.0")

Style = Literal[
    "newspaper", "dashboard", "minimalist",
    "scripture", "terminal", "darwin", "stranger-things",
    "spider-man", "pokemon",
]


def _today_local() -> date:
    """Today in the configured local timezone (Cloud Run runs UTC by default,
    so date.today() in MDT can be a day behind for late-night prints)."""
    s = get_settings()
    return datetime.now(ZoneInfo(s.timezone)).date()


def _style_for_day(d: date) -> str:
    s = get_settings()
    return [
        s.style_monday, s.style_tuesday, s.style_wednesday, s.style_thursday,
        s.style_friday, s.style_saturday, s.style_sunday,
    ][d.weekday()]


def _parse_countdowns(raw: str) -> list[Countdown]:
    out: list[Countdown] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or "@" not in entry:
            continue
        label, target = entry.rsplit("@", 1)
        try:
            out.append(Countdown(label=label.strip(), target=date.fromisoformat(target.strip())))
        except ValueError:
            logger.warning("countdown parse failed for %r", entry)
    return out


def _build_briefing(for_date: date | None = None) -> Briefing:
    """Compose the briefing from real sources where available, falling back
    to the sample for sources that are still stubbed or failed to fetch.
    """
    s = get_settings()
    today = for_date or _today_local()

    # Start with the sample as our base — it already has fake events,
    # tasks, jokes, quotes, CFM, year progress.
    b = sample_briefing(today=today)

    # Real weather (Open-Meteo, no auth).
    try:
        b.weather = fetch_weather(
            lat=s.weather_lat,
            lon=s.weather_lon,
            location_label=s.weather_location_label,
            tz=s.timezone,
        )
        logger.info("weather fetched ok")
    except Exception as exc:  # noqa: BLE001 — any fetch failure stays cosmetic
        logger.warning("weather fetch failed, using sample: %s", exc)

    # Real ticker (Yahoo Finance, no auth).
    if s.ticker_symbol:
        try:
            b.ticker = fetch_ticker(symbol=s.ticker_symbol)
            logger.info("ticker fetched ok: %s", b.ticker.symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ticker fetch failed, using sample: %s", exc)

    # Rotating prayer roll from env var (always overrides the sample).
    if s.prayer_rotation:
        b.prayer_group = prayer_group_for(today, s.prayer_rotation)

    # Countdowns from env var.
    if s.countdowns:
        try:
            parsed = _parse_countdowns(s.countdowns)
            if parsed:
                b.countdowns = parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("countdown parse failed: %s", exc)

    # Real Google Calendar (OAuth refresh-token flow).
    if all([s.google_oauth_client_id, s.google_oauth_client_secret, s.google_oauth_refresh_token]):
        try:
            cal_ids = [c.strip() for c in s.google_calendar_ids.split(",") if c.strip()]
            today_events, upcoming = fetch_today_and_upcoming(
                client_id=s.google_oauth_client_id,
                client_secret=s.google_oauth_client_secret,
                refresh_token=s.google_oauth_refresh_token,
                today=today,
                tz_name=s.timezone,
                calendar_ids=cal_ids,
            )
            b.events = today_events
            b.upcoming = upcoming
            logger.info("calendar fetched ok")
        except Exception as exc:  # noqa: BLE001
            logger.warning("calendar fetch failed, using sample: %s", exc)

    # Real Notion tasks.
    if all([s.notion_token, s.notion_task_database_id, s.notion_assignee_user_id]):
        try:
            b.tasks = fetch_top_tasks(
                notion_token=s.notion_token,
                database_id=s.notion_task_database_id,
                assignee_user_id=s.notion_assignee_user_id,
                today=today,
                limit=10,
            )
            logger.info("notion tasks fetched ok")
        except Exception as exc:  # noqa: BLE001
            logger.warning("notion fetch failed, using sample: %s", exc)

    return b


def _check_secret(secret: str | None) -> None:
    expected = get_settings().briefing_shared_secret
    if expected and secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


@app.get("/briefing")
def briefing(
    style: Style | None = None,
    secret: str | None = Query(default=None),
    fmt: Literal["pdf", "html"] = "pdf",
    for_date: str | None = Query(
        default=None, alias="date",
        description="YYYY-MM-DD to preview a specific day instead of today. "
                    "Notion, Calendar, CFM, prayer rotation, jokes, quote, "
                    "year-progress, and countdowns all respect this date. "
                    "Weather and ticker still show real-now values since "
                    "those don't make sense for future days.",
    ),
) -> Response:
    _check_secret(secret)
    target: date | None = None
    if for_date:
        try:
            target = date.fromisoformat(for_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date '{for_date}'. Use YYYY-MM-DD.",
            )
    b = _build_briefing(for_date=target)
    settings = get_settings()
    # Precedence: explicit ?style= > pinned STYLE env var > day-of-week
    chosen: Style = style or settings.style or _style_for_day(b.for_date)  # type: ignore[assignment]
    if fmt == "html":
        return Response(content=render_html(b, chosen), media_type="text/html")
    pdf = render_pdf(b, chosen)
    filename = f"briefing-{b.for_date.isoformat()}-{chosen}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/preview/{style}")
def preview(style: Style, fmt: Literal["pdf", "html"] = "pdf") -> Response:
    """Public preview using sample data only — no secret required, no live fetches."""
    b = sample_briefing()
    if fmt == "html":
        return Response(content=render_html(b, style), media_type="text/html")
    return Response(
        content=render_pdf(b, style),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="briefing-{style}-sample.pdf"'},
    )
