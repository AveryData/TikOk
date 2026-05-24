"""Yahoo Finance ticker fetcher. No API key required.

Uses the public chart endpoint:
    https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1y&interval=1d

Returns the latest close plus 7-day, 30-day, and year-to-date pct changes.
Returns None for any of those if there isn't enough history.

Caveats:
- Yahoo's endpoint is undocumented and could change. If it breaks, swap for
  Stooq (https://stooq.com/q/d/l/?s=spy.us&i=d) or Alpha Vantage.
- This container's egress policy may block Yahoo. In production on Cloud
  Run there's no allowlist, so it'll work.
- Outside market hours this returns the most recent trading day's close.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx

from app.models import TickerQuote


YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _ts_to_date(ts: int) -> date:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


def fetch_ticker(symbol: str = "SPY") -> TickerQuote:
    params = {"range": "1y", "interval": "1d", "includePrePost": "false"}
    with httpx.Client(timeout=10, headers=UA) as c:
        resp = c.get(YAHOO_URL.format(symbol=symbol), params=params)
        resp.raise_for_status()
        data = resp.json()

    result = data["chart"]["result"][0]
    timestamps: list[int] = result["timestamp"]
    closes: list[float | None] = result["indicators"]["quote"][0]["close"]

    series: list[tuple[date, float]] = [
        (_ts_to_date(ts), c)
        for ts, c in zip(timestamps, closes)
        if c is not None
    ]
    if not series:
        raise RuntimeError(f"No price data for {symbol}")

    series.sort(key=lambda r: r[0])
    last_date, last_close = series[-1]

    def _pct_change_from(target_date: date) -> float | None:
        prior = [s for s in series if s[0] <= target_date]
        if not prior:
            return None
        _, prior_close = prior[-1]
        if prior_close == 0:
            return None
        return (last_close - prior_close) / prior_close * 100

    return TickerQuote(
        symbol=symbol,
        price=last_close,
        as_of=last_date,
        pct_change_7d=_pct_change_from(last_date - timedelta(days=7)),
        pct_change_30d=_pct_change_from(last_date - timedelta(days=30)),
        pct_change_ytd=_pct_change_from(date(last_date.year, 1, 1) - timedelta(days=1)),
    )
