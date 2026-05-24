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

    # Countdowns from env var.
    if s.countdowns:
        try:
            parsed = _parse_countdowns(s.countdowns)
            if parsed:
                b.countdowns = parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("countdown parse failed: %s", exc)

    # TODO: wire Notion (b.tasks) and Google Calendar (b.events, b.upcoming)
    #       once tokens are configured. For now they remain sample data.

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
) -> Response:
    _check_secret(secret)
    b = _build_briefing()
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
