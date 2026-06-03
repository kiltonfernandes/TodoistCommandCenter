from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(slots=True)
class Project:
    id: str
    name: str
    color: str | None = None
    is_archived: bool = False
    order: int | None = None


@dataclass(slots=True)
class Task:
    id: str
    content: str
    project_id: str | None
    priority: int
    due_date: date | None
    created_at: str | None
    completed_at: str | None
    status: str
    labels: list[str]
    url: str | None = None
    description: str | None = None
    raw: dict[str, Any] | None = None
