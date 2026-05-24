"""Open-Meteo weather fetcher. No API key required."""
from __future__ import annotations

from datetime import date, datetime

import httpx

from app.models import Weather, WeatherHour


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


# Open-Meteo weather codes → short summary.
# Source: https://open-meteo.com/en/docs (WMO weather interpretation codes).
_CODE_SUMMARY: dict[int, str] = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Heavy showers",
    82: "Violent showers",
    95: "Thunderstorms",
    96: "Thunderstorms with hail",
    99: "Severe thunderstorms",
}


def fetch_weather(
    lat: float, lon: float, location_label: str, tz: str
) -> Weather:
    params = {
        "latitude": lat,
        "longitude": lon,
        "temperature_unit": "fahrenheit",
        "timezone": tz,
        "current": "temperature_2m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,sunrise,sunset",
        "hourly": "temperature_2m,precipitation_probability",
        "forecast_days": 1,
    }
    with httpx.Client(timeout=10) as client:
        resp = client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    today_str = date.today().isoformat()
    current = data["current"]
    daily = data["daily"]
    hourly = data["hourly"]

    code = int(daily["weather_code"][0])
    summary_main = _CODE_SUMMARY.get(code, "Unsettled")
    precip = int(daily["precipitation_probability_max"][0] or 0)
    summary = summary_main
    if precip >= 30 and code < 50:
        summary = f"{summary_main}, precip possible"

    sunrise_iso = daily["sunrise"][0]
    sunset_iso = daily["sunset"][0]
    sunrise = datetime.fromisoformat(sunrise_iso).strftime("%-I:%M %p").lower()
    sunset = datetime.fromisoformat(sunset_iso).strftime("%-I:%M %p").lower()

    hourly_buckets: list[WeatherHour] = []
    target_hours = [6, 8, 10, 12, 14, 16, 18, 20]
    for i, t in enumerate(hourly["time"]):
        dt = datetime.fromisoformat(t)
        if dt.strftime("%Y-%m-%d") != today_str:
            continue
        if dt.hour in target_hours:
            hourly_buckets.append(
                WeatherHour(
                    hour=dt.hour,
                    temp_f=int(round(hourly["temperature_2m"][i])),
                    precip_chance=int(hourly["precipitation_probability"][i] or 0),
                )
            )

    return Weather(
        location=location_label,
        summary=summary,
        high_f=int(round(daily["temperature_2m_max"][0])),
        low_f=int(round(daily["temperature_2m_min"][0])),
        current_f=int(round(current["temperature_2m"])),
        precip_chance_today=precip,
        sunrise=sunrise,
        sunset=sunset,
        hourly=hourly_buckets,
    )
