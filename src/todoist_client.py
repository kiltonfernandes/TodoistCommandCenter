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
        self.base_url = "https://api.todoist.com/rest/v2"

    def is_configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("TODOIST_API_TOKEN is not configured")
        return {"Authorization": f"Bearer {self.token}"}

    def fetch_projects(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/projects", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_project(self, project_id: str) -> dict:
        response = requests.get(f"{self.base_url}/projects/{project_id}", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_labels(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/labels", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_tasks(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/tasks", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def sync(self) -> TodoistSyncResult:
        projects = self.fetch_projects()
        tasks = self.fetch_tasks()
        labels = self.fetch_labels()
        return TodoistSyncResult(projects=projects, tasks=tasks, labels=labels, sync_token=datetime.now(timezone.utc).isoformat())
