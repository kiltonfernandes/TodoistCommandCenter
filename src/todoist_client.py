from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import requests


@dataclass
class TodoistSyncResult:
    projects: list[dict]
    tasks: list[dict]
    labels: list[dict]
    sync_token: str | None


class TodoistClient:
    def __init__(self, token: str | None):
        self.token = token
        self.base_url = "https://api.todoist.com/api/v1"

    def is_configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("TODOIST_API_TOKEN is not configured")
        return {"Authorization": f"Bearer {self.token}"}

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        response = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_all(self, path: str, params: dict | None = None) -> list[dict]:
        items: list[dict] = []
        cursor: str | None = None
        while True:
            query = dict(params or {})
            if cursor:
                query["cursor"] = cursor
            payload = self._get(path, params=query)
            if isinstance(payload, dict):
                page_items = payload.get("results", [])
                cursor = payload.get("next_cursor")
                items.extend(page_items)
                if not cursor:
                    break
            else:
                items.extend(payload)
                break
        return items

    def fetch_labels(self) -> list[dict]:
        return self._fetch_all("/labels")

    def fetch_projects(self) -> list[dict]:
        return self._fetch_all("/projects")

    def fetch_tasks(self) -> list[dict]:
        return self._fetch_all("/tasks")

    def sync(self) -> TodoistSyncResult:
        projects = self.fetch_projects()
        tasks = self.fetch_tasks()
        labels = self.fetch_labels()
        return TodoistSyncResult(projects=projects, tasks=tasks, labels=labels, sync_token=datetime.now(timezone.utc).isoformat())
