from __future__ import annotations

from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.models import Briefing
from app.render import narration

Style = Literal[
    "newspaper", "dashboard", "minimalist",
    "scripture", "terminal", "darwin", "stranger-things",
    "spider-man", "pokemon",
]

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _fmt_date_long(d) -> str:
    return d.strftime("%A, %B %-d, %Y")


def _fmt_date_short(d) -> str:
    return d.strftime("%a %b %-d")


def _fmt_due(d) -> str:
    return d.strftime("%a %-m/%-d") if d else ""


_env.filters["date_long"] = _fmt_date_long
_env.filters["date_short"] = _fmt_date_short
_env.filters["due"] = _fmt_due
_env.filters["hour_word"] = narration.hour_word
_env.filters["scripture_date"] = narration.scripture_date
_env.filters["with_th"] = narration._with_th
_env.filters["ascii_bar"] = narration.ascii_bar
_env.filters["time_log"] = lambda t: narration.time_log(t.hour, t.minute)
_env.filters["priority_marker"] = narration.priority_marker


def render_html(briefing: Briefing, style: Style) -> str:
    template = _env.get_template(f"{style}.html")
    return template.render(b=briefing)


def render_pdf(briefing: Briefing, style: Style) -> bytes:
    html = render_html(briefing, style)
    return HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf()
