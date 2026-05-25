from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Day-of-week persona rotation. Set STYLE in env to pin one style;
    # otherwise the day chooses. Manual ?style= on a request always wins.
    style: str | None = None
    timezone: str = "America/Denver"

    # Default rotation (Mon..Sun). Override via env var if you want.
    style_monday: str = "terminal"
    style_tuesday: str = "spider-man"
    style_wednesday: str = "darwin"
    style_thursday: str = "pokemon"
    style_friday: str = "stranger-things"
    style_saturday: str = "newspaper"
    style_sunday: str = "scripture"

    # Location for weather
    weather_lat: float = 40.3417
    weather_lon: float = -111.7186
    weather_location_label: str = "Lindon, UT"

    # Google Calendar (OAuth installed-app refresh token flow)
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_refresh_token: str | None = None
    # Comma-separated calendar IDs. Default to "primary" alias if unset.
    google_calendar_ids: str = "primary"

    # Notion
    notion_token: str | None = None
    notion_task_database_id: str | None = None
    notion_assignee_user_id: str | None = None

    # Optional auth on the endpoint itself
    briefing_shared_secret: str | None = None

    # Ticker symbol to show (set to empty string to hide)
    ticker_symbol: str = "SPY"

    # Countdowns: comma-separated "Label@YYYY-MM-DD" pairs.
    # e.g. "Bear Lake Brawl Half@2026-09-19,St. George Marathon@2026-10-03"
    countdowns: str = "Bear Lake Brawl Half Ironman@2026-09-19"

    # Rotating prayer roll. Groups separated by ';', names within each
    # group separated by ','. Cycle by day-of-year so groups recur every
    # len(groups) days. Override via PRAYER_ROTATION env var.
    prayer_rotation: str = (
        "Avery,Haley,Penny,Archer,Peach"
        ";Finch,Mckoy,Bridger,Austin,Hyrum,Caleb,Sean,Jordan,Taft,Tyson,Kalani"
        ";Dad,Mom,Elliott,Whitney,Graham"
        ";Jerry,Melissa,Bryson,Breanna,Cameron,Caden,Sierra"
        ";Austin,Pat,Hannah & Dillon,Brynn & Kobe,Steven,Dhawan"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
