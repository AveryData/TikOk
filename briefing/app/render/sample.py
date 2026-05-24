from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models import (
    Briefing,
    CalendarEvent,
    ComeFollowMe,
    Countdown,
    Priority,
    Task,
    TickerQuote,
    UpcomingEvent,
    Weather,
    WeatherHour,
)
from app.sources.extras import (
    come_follow_me_for,
    joke_for,
    quote_for,
    year_progress_for,
)


def sample_briefing(today: date | None = None) -> Briefing:
    today = today or date.today()

    def at(hour: int, minute: int = 0) -> datetime:
        return datetime.combine(today, datetime.min.time()).replace(
            hour=hour, minute=minute
        )

    events = [
        CalendarEvent("Deep work — Q3 launch deck", at(8, 0), at(10, 0)),
        CalendarEvent("1:1 with Jordan", at(10, 30), at(11, 0), location="Zoom"),
        CalendarEvent("Lunch — Maya", at(12, 0), at(13, 0), location="Sego Lily"),
        CalendarEvent("DCJ student office hours", at(14, 0), at(15, 0), location="Zoom"),
        CalendarEvent(
            "Course recording — Linear Regression",
            at(15, 30),
            at(17, 0),
            location="Home studio",
        ),
        CalendarEvent("Pickup kids", at(17, 15), at(17, 45)),
    ]

    def upcoming(days: int, hour: int, minute: int, title: str, loc: str | None = None):
        d = today + timedelta(days=days)
        when = datetime.combine(d, datetime.min.time()).replace(hour=hour, minute=minute)
        return UpcomingEvent(title=title, when=when, location=loc)

    upcoming_events = [
        upcoming(1, 9, 0, "Cohort 14 kickoff call", "Zoom"),
        upcoming(2, 18, 30, "Pizza night — family", "Main Street Pizza"),
        upcoming(3, 14, 0, "Podcast interview — Data Skeptic"),
        upcoming(4, 19, 0, "School concert", "School auditorium"),
        upcoming(6, 13, 0, "Birthday party — Eli", "Riverside Park"),
    ]

    tasks = [
        Task(
            "Finalize Cohort 14 welcome email sequence",
            Priority.ULTRA_HIGH,
            today - timedelta(days=2),
            "DCJ Marketing",
            is_past_due=True,
        ),
        Task("Review Notion task board automation rules", Priority.HIGH, today, "DCJ Ops"),
        Task("Record SQL window functions lesson", Priority.HIGH, today, "DCJ Course"),
        Task("Reply to enterprise inquiry — Allstate", Priority.HIGH, today + timedelta(days=1), "Sales"),
        Task("Update LinkedIn cohort case study", Priority.MEDIUM, today + timedelta(days=1), "DCJ Marketing"),
        Task("Draft Q3 OKRs", Priority.MEDIUM, today + timedelta(days=2), "DCJ Ops"),
        Task("Refactor onboarding email logic", Priority.MEDIUM, today + timedelta(days=2), "Engineering"),
        Task("Prep talking points for podcast interview", Priority.MEDIUM, today + timedelta(days=3), "Content"),
        Task("Annual review forms for team", Priority.LOW, today + timedelta(days=4), "DCJ Ops"),
        Task("Renew domain — datacareerjumpstart.com", Priority.LOW, today + timedelta(days=6), "Admin"),
    ]

    hourly = [
        WeatherHour(6, 48, 0),
        WeatherHour(8, 53, 0),
        WeatherHour(10, 61, 5),
        WeatherHour(12, 70, 10),
        WeatherHour(14, 76, 20),
        WeatherHour(16, 78, 40),
        WeatherHour(18, 74, 30),
        WeatherHour(20, 65, 10),
    ]

    weather = Weather(
        location="Lindon, UT",
        summary="Partly cloudy, afternoon thunderstorms possible",
        high_f=78,
        low_f=48,
        current_f=53,
        precip_chance_today=40,
        sunrise="6:02 am",
        sunset="8:47 pm",
        hourly=hourly,
    )

    # Come Follow Me: use real data if today is in the JSON, otherwise a
    # clearly-labeled placeholder so the section still demos.
    cfm = come_follow_me_for(today) or ComeFollowMe(
        week_label=today.strftime("%b %-d"),
        week_reference="[Run scripts/scrape_come_follow_me.py to populate]",
        week_theme=None,
        today_reference=None,
    )

    ticker = TickerQuote(
        symbol="SPY",
        price=587.42,
        as_of=today,
        pct_change_7d=1.4,
        pct_change_30d=3.2,
        pct_change_ytd=8.7,
    )

    countdowns = [
        Countdown(label="Bear Lake Brawl Half Ironman", target=date(2026, 9, 19)),
    ]

    return Briefing(
        for_date=today,
        greeting="Good morning, Avery & family",
        weather=weather,
        events=events,
        tasks=tasks,
        upcoming=upcoming_events,
        year_progress=year_progress_for(today),
        come_follow_me=cfm,
        joke=joke_for(today),
        quote=quote_for(today),
        ticker=ticker,
        countdowns=countdowns,
    )
