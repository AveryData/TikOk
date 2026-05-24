from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.models import Briefing
from app.render.pdf import render_html, render_pdf
from app.render.sample import sample_briefing

app = FastAPI(title="Daily Briefing Printer", version="0.1.0")

Style = Literal["newspaper", "dashboard", "minimalist", "scripture", "terminal"]


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
    chosen: Style = style or get_settings().style  # type: ignore[assignment]
    briefing = _build_briefing()
    if fmt == "html":
        html = render_html(briefing, chosen)
        return Response(content=html, media_type="text/html")
    pdf = render_pdf(briefing, chosen)
    filename = f"briefing-{briefing.for_date.isoformat()}.pdf"
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
