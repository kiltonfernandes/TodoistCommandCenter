from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json


@dataclass(slots=True)
class FocusedTask:
    task_id: str
    content: str
    project_name: str
    score: int
    reason: str
    due_date: str | None
    priority: int
    labels: list[str]


@dataclass(slots=True)
class ProjectNode:
    project_id: str
    name: str
    parent_id: str | None
    path: str
    root_name: str


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _priority_to_weight(priority: int) -> int:
    return {4: 4, 3: 3, 2: 2, 1: 1}.get(int(priority or 1), 1)


def _task_priority(task_row) -> int:
    return int(task_row.get("priority") or 1)


def build_project_index(project_rows) -> dict[str, ProjectNode]:
    raw = {row["project_id"]: row for row in project_rows}
    memo: dict[str, ProjectNode] = {}

    def build(project_id: str) -> ProjectNode:
        if project_id in memo:
            return memo[project_id]
        row = raw[project_id]
        parent_id = row["parent_id"]
        if parent_id and parent_id in raw:
            parent = build(parent_id)
            path = f"{parent.path} / {row['project_name']}"
            root_name = parent.root_name
        else:
            path = row["project_name"]
            root_name = row["project_name"]
        node = ProjectNode(
            project_id=project_id,
            name=row["project_name"],
            parent_id=parent_id,
            path=path,
            root_name=root_name,
        )
        memo[project_id] = node
        return node

    for project_id in raw:
        build(project_id)
    return memo


def compute_task_score(task_row, project_name: str | None, today: date | None = None) -> tuple[int, str]:
    today = today or date.today()
    due_date = _parse_date(task_row["due_date"])
    priority = _task_priority(task_row)
    base = _priority_to_weight(priority) * 18
    urgency = 0
    overdue = 0
    if due_date:
        delta = (today - due_date).days
        if delta > 0:
            overdue = min(delta * 10, 45)
        elif delta == 0:
            urgency = 18
        else:
            urgency = max(0, 12 - abs(delta) * 2)
    else:
        urgency = -10
    project_bonus = 1.0 + min(len(project_name or "") / 35.0, 0.7)
    score = int(max(0, min(100, (base + urgency + overdue) * project_bonus / 2.0)))
    reason_bits = [f"P{priority}"]
    if overdue:
        reason_bits.append(f"{overdue // 10} dia(s) em atraso")
    elif due_date:
        reason_bits.append("tem data definida")
    else:
        reason_bits.append("sem data")
    if task_row["status"] == "completed":
        reason_bits.append("concluída")
    return score, ", ".join(reason_bits)


def compute_metrics(tasks, projects) -> dict:
    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    project_index = build_project_index(projects)
    project_map = {project_id: node.path for project_id, node in project_index.items()}
    open_tasks = [t for t in tasks if t["status"] == "open"]
    completed_tasks = [t for t in tasks if t["status"] == "completed"]
    overdue_tasks = [t for t in open_tasks if _parse_date(t["due_date"]) and _parse_date(t["due_date"]) < today]
    no_date_tasks = [t for t in open_tasks if not t["due_date"]]
    due_today = [t for t in open_tasks if _parse_date(t["due_date"]) == today]
    due_next_7 = [
        t
        for t in open_tasks
        if _parse_date(t["due_date"]) and today <= _parse_date(t["due_date"]) <= today + timedelta(days=7)
    ]
    completed_today = [t for t in completed_tasks if t["completed_at"] and t["completed_at"].startswith(today.isoformat())]
    created_week = [
        t
        for t in tasks
        if t["created_at"] and datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")).date() >= this_week_start
    ]
    completed_week = [
        t
        for t in completed_tasks
        if t["completed_at"] and datetime.fromisoformat(t["completed_at"].replace("Z", "+00:00")).date() >= this_week_start
    ]
    completion_rate = round((len(completed_week) / max(1, len(created_week))) * 100, 1)
    focus_score = max(
        0,
        min(
            100,
            100
            - len(overdue_tasks) * 10
            - len(no_date_tasks) * 5
            - sum(1 for t in open_tasks if _task_priority(t) >= 4) * 2
            + len(completed_today) * 2,
        ),
    )
    return {
        "focus_score": int(focus_score),
        "completion_rate": completion_rate,
        "overdue_tasks": len(overdue_tasks),
        "open_tasks": len(open_tasks),
        "completed_today": len(completed_today),
        "created_week": len(created_week),
        "completed_week": len(completed_week),
        "due_today": len(due_today),
        "due_next_7": len(due_next_7),
        "no_date_tasks": len(no_date_tasks),
        "project_map": project_map,
        "project_index": project_index,
    }


def build_focus_list(tasks, projects, limit: int = 10) -> list[FocusedTask]:
    project_index = build_project_index(projects)
    focused = []
    for task in tasks:
        if task["status"] != "open":
            continue
        node = project_index.get(task["project_id"])
        project_name = node.path if node else "Sem projeto"
        score, reason = compute_task_score(task, project_name)
        focused.append(
            FocusedTask(
                task_id=task["task_id"],
                content=task["content"],
                project_name=project_name,
                score=score,
                reason=reason,
                due_date=task["due_date"],
                priority=_task_priority(task),
                labels=json.loads(task["labels_json"] or "[]"),
            )
        )
    focused.sort(key=lambda item: item.score, reverse=True)
    return focused[:limit]


def build_mission(tasks, projects) -> str:
    focused = build_focus_list(tasks, projects, limit=3)
    if not focused:
        return (
            "MISSÃO DE HOJE\n"
            "Objetivo: manter a base limpa e sincronizada.\n"
            "Tarefa: importar dados do Todoist e validar os indicadores."
        )
    project_name = focused[0].project_name
    lines = [
        "MISSÃO DE HOJE",
        f"Objetivo: reduzir o backlog de {project_name}.",
        "Tarefas críticas:",
    ]
    for item in focused:
        lines.append(f"- {item.content}")
    lines.append(f"Meta: concluir {min(3, len(focused))} tarefas de maior impacto.")
    return "\n".join(lines)
