from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class Priority(str, Enum):
    ULTRA_HIGH = "Ultra High"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    NONE = "None"


@dataclass
class CalendarEvent:
    title: str
    start: datetime | None
    end: datetime | None
    all_day: bool = False
    location: str | None = None

    @property
    def time_range(self) -> str:
        if self.all_day or self.start is None:
            return "All day"
        if self.end is None:
            return self.start.strftime("%-I:%M %p").lower()
        same_meridiem = self.start.strftime("%p") == self.end.strftime("%p")
        start_fmt = "%-I:%M" if same_meridiem else "%-I:%M %p"
        end_fmt = "%-I:%M %p"
        return f"{self.start.strftime(start_fmt)}–{self.end.strftime(end_fmt)}".lower()


@dataclass
class Task:
    title: str
    priority: Priority = Priority.NONE
    due: date | None = None
    project: str | None = None
    is_past_due: bool = False


@dataclass
class WeatherHour:
    hour: int
    temp_f: int
    precip_chance: int


@dataclass
class Weather:
    location: str
    summary: str
    high_f: int
    low_f: int
    current_f: int
    precip_chance_today: int
    sunrise: str
    sunset: str
    hourly: list[WeatherHour] = field(default_factory=list)


@dataclass
class Briefing:
    for_date: date
    greeting: str
    weather: Weather
    events: list[CalendarEvent]
    tasks: list[Task]
