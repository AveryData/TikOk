from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    style: str = "newspaper"  # newspaper | dashboard | minimalist
    timezone: str = "America/Denver"

    # Location for weather
    weather_lat: float = 40.3417
    weather_lon: float = -111.7186
    weather_location_label: str = "Lindon, UT"

    # Google Calendar
    google_calendar_id: str = "primary"
    google_oauth_client_secrets_path: str | None = None
    google_oauth_token_path: str | None = None

    # Notion
    notion_token: str | None = None
    notion_task_database_id: str | None = None
    notion_assignee_user_id: str | None = None

    # Optional auth on the endpoint itself
    briefing_shared_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
