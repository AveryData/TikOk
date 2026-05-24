"""Notion task source. Stub for now — wire up after style is chosen.

Will query the DCJ Task Board database filtered to the configured assignee,
exclude statuses Complete and Draft, and rank by:
  1. past-due (oldest first)
  2. due today
  3. remaining sorted by priority (Ultra High > High > Medium > Low > None)
     then by due date ascending.
Returns the top 10.
"""
from __future__ import annotations

from datetime import date

from app.models import Task


def fetch_top_tasks(
    for_date: date,
    notion_token: str,
    database_id: str,
    assignee_user_id: str,
    limit: int = 10,
) -> list[Task]:
    raise NotImplementedError(
        "Notion source not yet wired. "
        "See README for Notion integration setup."
    )
