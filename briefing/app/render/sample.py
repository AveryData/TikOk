from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models import (
    Briefing,
    CalendarEvent,
    Priority,
    Task,
    Weather,
    WeatherHour,
)


def sample_briefing(today: date | None = None) -> Briefing:
    today = today or date.today()

    def at(hour: int, minute: int = 0) -> datetime:
        return datetime.combine(today, datetime.min.time()).replace(
            hour=hour, minute=minute
        )

    events = [
        CalendarEvent("Deep work — Q3 launch deck", at(8, 0), at(10, 0)),
        CalendarEvent(
            "1:1 with Jordan", at(10, 30), at(11, 0), location="Zoom"
        ),
        CalendarEvent("Lunch — Maya", at(12, 0), at(13, 0), location="Sego Lily"),
        CalendarEvent(
            "DCJ student office hours",
            at(14, 0),
            at(15, 0),
            location="Zoom",
        ),
        CalendarEvent(
            "Course recording — Linear Regression",
            at(15, 30),
            at(17, 0),
            location="Home studio",
        ),
        CalendarEvent("Pickup kids", at(17, 15), at(17, 45)),
    ]

    tasks = [
        Task(
            "Finalize Cohort 14 welcome email sequence",
            Priority.ULTRA_HIGH,
            today - timedelta(days=2),
            "DCJ Marketing",
            is_past_due=True,
        ),
        Task(
            "Review Notion task board automation rules",
            Priority.HIGH,
            today,
            "DCJ Ops",
        ),
        Task("Record SQL window functions lesson", Priority.HIGH, today, "DCJ Course"),
        Task(
            "Reply to enterprise inquiry — Allstate",
            Priority.HIGH,
            today + timedelta(days=1),
            "Sales",
        ),
        Task(
            "Update LinkedIn cohort case study",
            Priority.MEDIUM,
            today + timedelta(days=1),
            "DCJ Marketing",
        ),
        Task(
            "Draft Q3 OKRs",
            Priority.MEDIUM,
            today + timedelta(days=2),
            "DCJ Ops",
        ),
        Task(
            "Refactor onboarding email logic",
            Priority.MEDIUM,
            today + timedelta(days=2),
            "Engineering",
        ),
        Task(
            "Prep talking points for podcast interview",
            Priority.MEDIUM,
            today + timedelta(days=3),
            "Content",
        ),
        Task(
            "Annual review forms for team",
            Priority.LOW,
            today + timedelta(days=4),
            "DCJ Ops",
        ),
        Task(
            "Renew domain — datacareerjumpstart.com",
            Priority.LOW,
            today + timedelta(days=6),
            "Admin",
        ),
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

    return Briefing(
        for_date=today,
        greeting="Good morning, Avery",
        weather=weather,
        events=events,
        tasks=tasks,
    )
