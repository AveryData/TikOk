"""Health Auto Export receiver + reader.

HAE pushes the trailing 7 days of selected metrics each morning. We parse
the payload into a single :class:`HealthSnapshot` (latest day's numbers
plus 7-day trends), write it to GCS, and let the briefing render pull
the latest snapshot back at print time.

The HAE JSON shape is:

    {
      "data": {
        "metrics": [
          {"name": "step_count", "units": "count",
           "data": [{"date": "2026-06-03 00:00:00 -0600", "qty": 9842}, ...]},
          {"name": "sleep_analysis", "units": "hr",
           "data": [{"date": "...", "asleep": 7.2, "deep": 1.0,
                     "rem": 1.3, ...}, ...]},
          ...
        ],
        "workouts": [
          {"name": "Cycling", "start": "...", "end": "...",
           "distance": {"qty": 18.4, "units": "mi"}}, ...
        ]
      }
    }

Metric names vary slightly between HAE versions, so the parser looks
each metric up by a list of aliases instead of an exact key.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.models import HealthSnapshot, WorkoutTotals

logger = logging.getLogger("briefing.health")

# Each metric maps to the candidate names HAE may use. First match wins.
_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "steps": ("step_count", "steps"),
    "active_energy": ("active_energy", "active_energy_burned"),
    "resting_hr": ("resting_heart_rate",),
    "hrv": ("heart_rate_variability", "heart_rate_variability_sdnn"),
    "weight": ("weight_body_mass", "body_mass", "weight"),
    "vo2_max": ("vo2_max", "cardio_fitness"),
    "sleep": ("sleep_analysis",),
}

# How to roll multiple same-day samples into a single daily value.
# HAE may export either pre-aggregated daily totals (one point per day)
# or raw intraday samples (hundreds of points per day); both reduce to
# one number per metric per day with the right operator.
_AGG_SUM = "sum"
_AGG_MEAN = "mean"
_AGG_LATEST = "latest"

_METRIC_AGG: dict[str, str] = {
    "steps": _AGG_SUM,
    "active_energy": _AGG_SUM,
    "resting_hr": _AGG_LATEST,
    "hrv": _AGG_MEAN,
    "weight": _AGG_LATEST,
    "vo2_max": _AGG_LATEST,
}

_RUN_KEYWORDS = ("run",)
_BIKE_KEYWORDS = ("cycling", "bike", "biking")
_SWIM_KEYWORDS = ("swim",)


def _parse_hae_datetime(s: str) -> datetime:
    """HAE dates look like '2026-06-03 00:00:00 -0600'."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")


def _find_metric(metrics: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    aliases = _METRIC_ALIASES[key]
    for m in metrics:
        if m.get("name") in aliases:
            return m
    return None


def _daily_values(
    metric: dict[str, Any] | None, agg: str, field: str = "qty"
) -> list[tuple[date, float]]:
    """Group raw points by calendar date and aggregate within each day.

    HAE's raw export can have hundreds of intraday samples per metric;
    its aggregated export has one per day. Both shapes collapse to a
    list of (day, value) once aggregated with the right operator.
    """
    if not metric:
        return []
    by_day: dict[date, list[float]] = {}
    for p in metric.get("data") or []:
        v = p.get(field)
        if v is None:
            continue
        try:
            dt = _parse_hae_datetime(p["date"])
        except (KeyError, ValueError):
            continue
        by_day.setdefault(dt.date(), []).append(float(v))
    out: list[tuple[date, float]] = []
    for d in sorted(by_day):
        vs = by_day[d]
        if agg == _AGG_SUM:
            out.append((d, sum(vs)))
        elif agg == _AGG_MEAN:
            out.append((d, sum(vs) / len(vs)))
        else:  # _AGG_LATEST: HAE points within a day already come in time order
            out.append((d, vs[-1]))
    return out


def _latest_and_avg(
    metric: dict[str, Any] | None, key: str
) -> tuple[float | None, float | None]:
    """Return (latest day's value, mean over last 7 days)."""
    pairs = _daily_values(metric, _METRIC_AGG[key])
    if not pairs:
        return None, None
    latest = pairs[-1][1]
    window = pairs[-7:]
    avg = sum(v for _, v in window) / len(window)
    return latest, avg


def _kg_to_lb(kg: float | None) -> float | None:
    return None if kg is None else kg * 2.2046226218


def _parse_sleep(metric: dict[str, Any] | None) -> tuple[float | None, float | None, float | None]:
    """Most recent sleep_analysis entry → (total, deep, rem) hours."""
    if not metric:
        return None, None, None
    points = metric.get("data") or []
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for p in points:
        try:
            dt = _parse_hae_datetime(p["date"])
        except (KeyError, ValueError):
            continue
        parsed.append((dt, p))
    if not parsed:
        return None, None, None
    parsed.sort(key=lambda x: x[0])
    latest = parsed[-1][1]
    # HAE sometimes reports `asleep` and `inBed` as 0 even when the night
    # was tracked — fall through truthy checks to totalSleep, and as a
    # last resort sum the stage breakdown.
    total = latest.get("asleep") or latest.get("totalSleep") or latest.get("inBed")
    if not total:
        stages = [latest.get(k) or 0 for k in ("deep", "rem", "core")]
        if any(stages):
            total = sum(stages)
    deep = latest.get("deep")
    rem = latest.get("rem")
    return (
        float(total) if total else None,
        float(deep) if deep is not None else None,
        float(rem) if rem is not None else None,
    )


def _sum_workouts(
    workouts: list[dict[str, Any]], since: datetime
) -> WorkoutTotals:
    """Sum distance by sport over the last 7 days."""
    totals = WorkoutTotals(window_days=7)
    for w in workouts:
        name = (w.get("name") or "").lower()
        try:
            end = _parse_hae_datetime(w["end"]) if w.get("end") else _parse_hae_datetime(w["start"])
        except (KeyError, ValueError):
            continue
        if end < since:
            continue
        dist = (w.get("distance") or {}).get("qty")
        if dist is None:
            miles = 0.0
        else:
            units = (w.get("distance") or {}).get("units", "mi").lower()
            miles = float(dist) if units in ("mi", "mile", "miles") else float(dist) * 0.6213711922
        if any(k in name for k in _RUN_KEYWORDS):
            totals.miles_run += miles
            totals.run_count += 1
        elif any(k in name for k in _BIKE_KEYWORDS):
            totals.miles_biked += miles
            totals.bike_count += 1
        elif any(k in name for k in _SWIM_KEYWORDS):
            totals.miles_swam += miles
            totals.swim_count += 1
    return totals


def parse_hae_payload(payload: dict[str, Any], received_at: datetime) -> HealthSnapshot:
    """Turn a HAE JSON push into a HealthSnapshot."""
    data = payload.get("data") or {}
    metrics: list[dict[str, Any]] = data.get("metrics") or []
    workouts: list[dict[str, Any]] = data.get("workouts") or []

    steps_latest, _ = _latest_and_avg(_find_metric(metrics, "steps"), "steps")
    energy_latest, _ = _latest_and_avg(_find_metric(metrics, "active_energy"), "active_energy")
    rhr_latest, rhr_avg = _latest_and_avg(_find_metric(metrics, "resting_hr"), "resting_hr")
    hrv_latest, hrv_avg = _latest_and_avg(_find_metric(metrics, "hrv"), "hrv")
    weight_metric = _find_metric(metrics, "weight")
    weight_latest, weight_avg = _latest_and_avg(weight_metric, "weight")
    weight_units = (weight_metric or {}).get("units", "lb").lower()
    if weight_units in ("kg", "kilogram", "kilograms"):
        weight_latest = _kg_to_lb(weight_latest)
        weight_avg = _kg_to_lb(weight_avg)
    weight_delta = (
        None
        if weight_latest is None or weight_avg is None
        else weight_latest - weight_avg
    )
    vo2_latest, _ = _latest_and_avg(_find_metric(metrics, "vo2_max"), "vo2_max")
    sleep_total, sleep_deep, sleep_rem = _parse_sleep(_find_metric(metrics, "sleep"))

    since = received_at - timedelta(days=7)
    workout_totals = _sum_workouts(workouts, since=since) if workouts else None

    # Figure out which day this snapshot represents — the most recent date
    # we saw in any metric, falling back to "yesterday" relative to push time.
    snapshot_date = _infer_snapshot_date(metrics) or (received_at.date() - timedelta(days=1))

    return HealthSnapshot(
        pushed_at=received_at,
        snapshot_date=snapshot_date,
        steps=int(steps_latest) if steps_latest is not None else None,
        active_energy_kcal=int(energy_latest) if energy_latest is not None else None,
        resting_hr_bpm=rhr_latest,
        resting_hr_7d_avg=rhr_avg,
        hrv_ms=hrv_latest,
        hrv_7d_avg=hrv_avg,
        weight_lb=weight_latest,
        weight_7d_delta_lb=weight_delta,
        vo2_max=vo2_latest,
        sleep_hours=sleep_total,
        sleep_deep_hours=sleep_deep,
        sleep_rem_hours=sleep_rem,
        workouts_7d=workout_totals,
    )


def _infer_snapshot_date(metrics: list[dict[str, Any]]) -> date | None:
    latest: datetime | None = None
    for m in metrics:
        for p in m.get("data") or []:
            try:
                dt = _parse_hae_datetime(p["date"])
            except (KeyError, ValueError):
                continue
            if latest is None or dt > latest:
                latest = dt
    return latest.date() if latest else None


# --- GCS storage --------------------------------------------------------

_LATEST_KEY = "health/latest.json"


def _snapshot_to_jsonable(s: HealthSnapshot) -> dict[str, Any]:
    d = asdict(s)
    d["pushed_at"] = s.pushed_at.isoformat()
    d["snapshot_date"] = s.snapshot_date.isoformat()
    return d


def _snapshot_from_jsonable(d: dict[str, Any]) -> HealthSnapshot:
    w = d.get("workouts_7d")
    workouts = WorkoutTotals(**w) if w else None
    return HealthSnapshot(
        pushed_at=datetime.fromisoformat(d["pushed_at"]),
        snapshot_date=date.fromisoformat(d["snapshot_date"]),
        steps=d.get("steps"),
        active_energy_kcal=d.get("active_energy_kcal"),
        resting_hr_bpm=d.get("resting_hr_bpm"),
        resting_hr_7d_avg=d.get("resting_hr_7d_avg"),
        hrv_ms=d.get("hrv_ms"),
        hrv_7d_avg=d.get("hrv_7d_avg"),
        weight_lb=d.get("weight_lb"),
        weight_7d_delta_lb=d.get("weight_7d_delta_lb"),
        vo2_max=d.get("vo2_max"),
        sleep_hours=d.get("sleep_hours"),
        sleep_deep_hours=d.get("sleep_deep_hours"),
        sleep_rem_hours=d.get("sleep_rem_hours"),
        workouts_7d=workouts,
    )


def store_snapshot(bucket_name: str, snapshot: HealthSnapshot, raw: dict[str, Any]) -> None:
    """Persist both the parsed snapshot and the raw HAE payload to GCS.

    Layout:
        health/raw/<iso-timestamp>.json   — every push, audit trail
        health/snapshots/<YYYY-MM-DD>.json — one per snapshot day (overwrites)
        health/latest.json                — pointer the render reads
    """
    from google.cloud import storage  # lazy: not needed for local dev

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    ts = snapshot.pushed_at.strftime("%Y%m%dT%H%M%SZ")
    parsed_blob = _snapshot_to_jsonable(snapshot)

    bucket.blob(f"health/raw/{ts}.json").upload_from_string(
        json.dumps(raw), content_type="application/json"
    )
    bucket.blob(f"health/snapshots/{snapshot.snapshot_date.isoformat()}.json").upload_from_string(
        json.dumps(parsed_blob), content_type="application/json"
    )
    bucket.blob(_LATEST_KEY).upload_from_string(
        json.dumps(parsed_blob), content_type="application/json"
    )


def load_latest_snapshot(bucket_name: str, max_age_hours: int) -> HealthSnapshot | None:
    """Read the pointer object. Returns None if missing or too old."""
    from google.cloud import storage

    client = storage.Client()
    blob = client.bucket(bucket_name).blob(_LATEST_KEY)
    if not blob.exists():
        return None
    snapshot = _snapshot_from_jsonable(json.loads(blob.download_as_text()))
    age = datetime.now(timezone.utc) - snapshot.pushed_at
    if age > timedelta(hours=max_age_hours):
        logger.info("health snapshot is stale (%s old), skipping", age)
        return None
    return snapshot
