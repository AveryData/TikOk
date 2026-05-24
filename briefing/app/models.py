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
class UpcomingEvent:
    """A calendar event in the next ~7 days (not today)."""
    title: str
    when: datetime
    location: str | None = None

    @property
    def day_label(self) -> str:
        return self.when.strftime("%a %-m/%-d")

    @property
    def time_label(self) -> str:
        if self.when.hour == 0 and self.when.minute == 0:
            return ""
        # Compact: "6:30p" / "9a" — saves space in narrow columns.
        if self.when.minute == 0:
            return self.when.strftime("%-I%p").lower().replace("m", "")
        return self.when.strftime("%-I:%M%p").lower().replace("m", "")


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
class YearProgress:
    day_of_year: int
    days_in_year: int

    @property
    def pct(self) -> float:
        return self.day_of_year / self.days_in_year * 100

    @property
    def pct_label(self) -> str:
        return f"{self.pct:.1f}%"


@dataclass
class ComeFollowMe:
    week_label: str          # e.g. "May 18–24"
    week_reference: str      # e.g. "Genesis 12–17"
    week_theme: str | None   # e.g. "Abraham and Sarah"
    today_reference: str | None  # e.g. "Genesis 12:1–8"


@dataclass
class Quote:
    text: str
    attribution: str | None = None


@dataclass
class TickerQuote:
    symbol: str          # "SPY"
    price: float         # latest close
    as_of: date          # date of that close
    pct_change_7d: float | None
    pct_change_30d: float | None
    pct_change_ytd: float | None

    @staticmethod
    def _fmt(pct: float | None) -> str:
        if pct is None:
            return "—"
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    @property
    def label_7d(self) -> str: return self._fmt(self.pct_change_7d)
    @property
    def label_30d(self) -> str: return self._fmt(self.pct_change_30d)
    @property
    def label_ytd(self) -> str: return self._fmt(self.pct_change_ytd)


@dataclass
class Countdown:
    label: str       # e.g. "Bear Lake Half Ironman"
    target: date

    def days_until(self, today: date) -> int:
        return (self.target - today).days


@dataclass
class Briefing:
    for_date: date
    greeting: str
    weather: Weather
    events: list[CalendarEvent]
    tasks: list[Task]
    upcoming: list[UpcomingEvent] = field(default_factory=list)
    year_progress: YearProgress | None = None
    come_follow_me: ComeFollowMe | None = None
    joke: str | None = None
    quote: Quote | None = None
    ticker: TickerQuote | None = None
    countdowns: list[Countdown] = field(default_factory=list)
