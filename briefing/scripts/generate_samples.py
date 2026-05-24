"""Render the three style options as sample PDFs using fake data."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Make `app` importable when run from briefing/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.render.pdf import render_pdf  # noqa: E402
from app.render.sample import sample_briefing  # noqa: E402


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)

    briefing = sample_briefing(today=date(2026, 5, 24))

    for style in ("newspaper", "dashboard", "minimalist"):
        pdf_bytes = render_pdf(briefing, style)  # type: ignore[arg-type]
        out_path = out_dir / f"briefing-{style}.pdf"
        out_path.write_bytes(pdf_bytes)
        print(f"wrote {out_path} ({len(pdf_bytes):,} bytes)")


if __name__ == "__main__":
    main()
