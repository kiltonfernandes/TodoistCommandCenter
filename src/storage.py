from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    parent_id TEXT,
    color TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0,
    project_order INTEGER,
    raw_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    project_id TEXT,
    priority INTEGER NOT NULL DEFAULT 1,
    due_date TEXT,
    created_at TEXT,
    completed_at TEXT,
    status TEXT NOT NULL,
    labels_json TEXT NOT NULL DEFAULT '[]',
    url TEXT,
    description TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT PRIMARY KEY,
    sync_token TEXT,
    last_sync TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics_daily (
    metric_date TEXT PRIMARY KEY,
    focus_score INTEGER NOT NULL,
    completion_rate REAL NOT NULL,
    overdue_tasks INTEGER NOT NULL,
    open_tasks INTEGER NOT NULL,
    completed_today INTEGER NOT NULL,
    created_week INTEGER NOT NULL,
    completed_week INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def fetch_projects(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY project_name").fetchall()
        return [dict(row) for row in rows]

    def fetch_tasks(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def fetch_metrics_history(self, limit: int = 14) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM metrics_daily ORDER BY metric_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_projects(self, projects: list[dict]) -> None:
        now = datetime.utcnow().isoformat()
        with self.connect() as conn:
            for project in projects:
                project_id = project.get("project_id") or project.get("id")
                project_name = project.get("project_name") or project.get("name") or ""
                conn.execute(
                    """
                    INSERT INTO projects(project_id, project_name, parent_id, color, is_archived, project_order, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        project_name=excluded.project_name,
                        parent_id=excluded.parent_id,
                        color=excluded.color,
                        is_archived=excluded.is_archived,
                        project_order=excluded.project_order,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        project_id,
                        project_name,
                        project.get("parent_id"),
                        project.get("color"),
                        int(bool(project.get("is_archived", False))),
                        project.get("order"),
                        json.dumps(project, ensure_ascii=False),
                        now,
                    ),
                )

    def replace_tasks(self, tasks: list[dict]) -> None:
        now = datetime.utcnow().isoformat()
        with self.connect() as conn:
            for task in tasks:
                due = task.get("due") or {}
                due_date = due.get("date")
                created_at = task.get("added_at") or task.get("created_at")
                task_id = task.get("task_id") or task.get("id")
                conn.execute(
                    """
                    INSERT INTO tasks(task_id, content, project_id, priority, due_date, created_at, completed_at, status, labels_json, url, description, raw_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        content=excluded.content,
                        project_id=excluded.project_id,
                        priority=excluded.priority,
                        due_date=excluded.due_date,
                        created_at=excluded.created_at,
                        completed_at=excluded.completed_at,
                        status=excluded.status,
                        labels_json=excluded.labels_json,
                        url=excluded.url,
                        description=excluded.description,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        task_id,
                        task.get("content", ""),
                        task.get("project_id"),
                        int(task.get("priority", 1)),
                        due_date,
                        created_at,
                        task.get("completed_at"),
                        "completed" if task.get("checked") or task.get("is_completed") else "open",
                        json.dumps(task.get("labels", []), ensure_ascii=False),
                        task.get("url"),
                        task.get("description"),
                        json.dumps(task, ensure_ascii=False),
                        now,
                    ),
                )

    def replace_sync_state(self, source: str, sync_token: str | None) -> None:
        now = datetime.utcnow().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_state(source, sync_token, last_sync)
                VALUES (?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    sync_token=excluded.sync_token,
                    last_sync=excluded.last_sync
                """,
                (source, sync_token, now),
            )

    def save_metrics(self, metric_date: date, metrics: dict) -> None:
        now = datetime.utcnow().isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO metrics_daily(metric_date, focus_score, completion_rate, overdue_tasks, open_tasks, completed_today, created_week, completed_week, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric_date) DO UPDATE SET
                    focus_score=excluded.focus_score,
                    completion_rate=excluded.completion_rate,
                    overdue_tasks=excluded.overdue_tasks,
                    open_tasks=excluded.open_tasks,
                    completed_today=excluded.completed_today,
                    created_week=excluded.created_week,
                    completed_week=excluded.completed_week,
                    updated_at=excluded.updated_at
                """,
                (
                    metric_date.isoformat(),
                    metrics["focus_score"],
                    metrics["completion_rate"],
                    metrics["overdue_tasks"],
                    metrics["open_tasks"],
                    metrics["completed_today"],
                    metrics["created_week"],
                    metrics["completed_week"],
                    now,
                ),
            )
