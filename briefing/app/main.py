from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.models import Briefing
from app.render.pdf import render_html, render_pdf
from app.render.sample import sample_briefing

app = FastAPI(title="A Record of Our Day", version="0.2.0")

Style = Literal[
    "newspaper", "dashboard", "minimalist",
    "scripture", "terminal", "darwin", "stranger-things",
    "spider-man", "pokemon",
]


def _style_for_day(d: date) -> str:
    s = get_settings()
    return [
        s.style_monday, s.style_tuesday, s.style_wednesday, s.style_thursday,
        s.style_friday, s.style_saturday, s.style_sunday,
    ][d.weekday()]


def _build_briefing(for_date: date | None = None) -> Briefing:
    # TODO: once Notion + Calendar sources are wired, replace this with
    #       real-data assembly. For now we serve the sample.
    return sample_briefing(today=for_date)


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
    briefing = _build_briefing()
    settings = get_settings()
    # Precedence: explicit ?style= > pinned STYLE env var > day-of-week
    chosen: Style = style or settings.style or _style_for_day(briefing.for_date)  # type: ignore[assignment]
    if fmt == "html":
        html = render_html(briefing, chosen)
        return Response(content=html, media_type="text/html")
    pdf = render_pdf(briefing, chosen)
    filename = f"briefing-{briefing.for_date.isoformat()}-{chosen}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/preview/{style}")
def preview(style: Style, fmt: Literal["pdf", "html"] = "pdf") -> Response:
    """Public preview endpoint using sample data — no secret required."""
    briefing = sample_briefing()
    if fmt == "html":
        return Response(content=render_html(briefing, style), media_type="text/html")
    return Response(
        content=render_pdf(briefing, style),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="briefing-{style}-sample.pdf"'},
    )
