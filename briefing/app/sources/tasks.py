"""Notion task source. Queries the DCJ Task Board for the user's top-10
most urgent open tasks.

Filters (mirror the "My Tasks" view in Notion):
  - Assignee = the configured user
  - Status NOT IN [Complete group, Draft]

Ranking (computed in Python after fetch since Notion's API can't do this
ordering natively):
  1. Past-due first, oldest first
  2. Then due today
  3. Then remaining sorted by priority (Ultra High > High > Medium > Low > Ultra Low > None > Ignore)
     and within priority, by due date ascending (None last)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.models import Priority, Task

logger = logging.getLogger("briefing.notion")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Priority labels as they appear in the DCJ Task Board (note the trailing
# space on "High " and the variant "High" — both exist in Avery's data).
_PRIORITY_RANK: dict[str, tuple[int, Priority]] = {
    "Ultra High 🔥": (0, Priority.ULTRA_HIGH),
    "High ":         (1, Priority.HIGH),   # legacy with trailing space
    "High":          (1, Priority.HIGH),
    "Medium":        (2, Priority.MEDIUM),
    "Low":           (3, Priority.LOW),
    "Ultra Low":     (4, Priority.LOW),
    "Ignore":        (99, Priority.NONE),
    "":              (5, Priority.NONE),
}

# Status values we exclude (everything in the Complete group, plus Draft).
_EXCLUDED_STATUSES = {"Done", "Cancelled", "Recurring", "Draft"}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _extract_title(page: dict[str, Any]) -> str:
    title_prop = page["properties"].get("Task name") or page["properties"].get("Name")
    if not title_prop:
        return "(untitled)"
    parts = title_prop.get("title") or []
    return "".join(p.get("plain_text", "") for p in parts).strip() or "(untitled)"


def _extract_priority(page: dict[str, Any]) -> str:
    sel = page["properties"].get("Priority", {}).get("select")
    return (sel or {}).get("name") or ""


def _extract_status(page: dict[str, Any]) -> str:
    st = page["properties"].get("Status", {}).get("status")
    return (st or {}).get("name") or ""


def _extract_due(page: dict[str, Any]) -> date | None:
    d = page["properties"].get("Due date", {}).get("date")
    if not d or not d.get("start"):
        return None
    raw = d["start"]
    try:
        # Notion may give "YYYY-MM-DD" or full ISO datetime.
        if "T" in raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _extract_project_name(page: dict[str, Any]) -> str | None:
    """The 'DCJ Project' property is a relation. Notion API returns only the
    related page IDs, not their titles — fetching the project name would
    require an extra API call per task. For now we fall back to the
    Department multi-select for the project label, since that's already in
    the schema response and avoids N+1."""
    dept = page["properties"].get("Department", {}).get("multi_select") or []
    if dept:
        return dept[0].get("name")
    return None


def _rank_key(t: dict[str, Any], today: date) -> tuple[int, ...]:
    """Sort key. Lower = more urgent."""
    due = t["due"]
    pri_rank = _PRIORITY_RANK.get(t["priority_raw"], (5, Priority.NONE))[0]
    if due is not None and due < today:
        # Past due: oldest first, then by priority.
        return (0, due.toordinal(), pri_rank)
    if due == today:
        return (1, pri_rank, 0)
    if due is not None:
        return (2, pri_rank, due.toordinal())
    return (3, pri_rank, 0)


def fetch_top_tasks(
    notion_token: str,
    database_id: str,
    assignee_user_id: str,
    today: date,
    limit: int = 10,
) -> list[Task]:
    """Query the database, filter, rank, and return the top N tasks."""
    # Notion's "data source" model (2025+) requires hitting /v1/databases/{id}/query
    # which still works for both classic and new-style databases.
    url = f"{NOTION_API}/databases/{database_id}/query"
    body = {
        "filter": {
            "and": [
                {"property": "Assignee", "people": {"contains": assignee_user_id}},
                {"property": "Status", "status": {"does_not_equal": "Done"}},
                {"property": "Status", "status": {"does_not_equal": "Cancelled"}},
                {"property": "Status", "status": {"does_not_equal": "Recurring"}},
                {"property": "Status", "status": {"does_not_equal": "Draft"}},
            ]
        },
        "page_size": 100,  # over-fetch then rank locally
    }

    collected: list[dict[str, Any]] = []
    cursor: str | None = None
    with httpx.Client(timeout=15, headers=_headers(notion_token)) as client:
        for _ in range(5):  # safety cap on pagination
            if cursor:
                body["start_cursor"] = cursor
            resp = client.post(url, json=body)
            resp.raise_for_status()
            payload = resp.json()
            for page in payload.get("results", []):
                title = _extract_title(page)
                priority_raw = _extract_priority(page)
                if priority_raw == "Ignore":
                    continue
                due = _extract_due(page)
                status_name = _extract_status(page)
                if status_name in _EXCLUDED_STATUSES:
                    continue
                collected.append({
                    "title": title,
                    "priority_raw": priority_raw,
                    "priority": _PRIORITY_RANK.get(priority_raw, (5, Priority.NONE))[1],
                    "due": due,
                    "project": _extract_project_name(page),
                    "is_past_due": due is not None and due < today,
                })
            if not payload.get("has_more"):
                break
            cursor = payload.get("next_cursor")

    collected.sort(key=lambda t: _rank_key(t, today))
    top = collected[:limit]
    logger.info("notion: fetched %d tasks, returning top %d", len(collected), len(top))
    return [
        Task(
            title=t["title"],
            priority=t["priority"],
            due=t["due"],
            project=t["project"],
            is_past_due=t["is_past_due"],
        )
        for t in top
    ]
