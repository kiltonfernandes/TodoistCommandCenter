from __future__ import annotations

from datetime import date

import pandas as pd


def _parse_datetime_series(series):
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None)


def prepare_task_frame(tasks, project_index):
    task_df = pd.DataFrame([dict(task) for task in tasks])
    if task_df.empty:
        return task_df
    defaults = {
        "task_id": "",
        "content": "",
        "project_id": None,
        "priority": 1,
        "due_date": None,
        "created_at": None,
        "completed_at": None,
        "status": "open",
        "labels_json": "[]",
    }
    for column, default in defaults.items():
        if column not in task_df.columns:
            task_df[column] = default
    project_path_map = {project_id: node.path for project_id, node in project_index.items()}
    root_name_map = {project_id: node.root_name for project_id, node in project_index.items()}
    task_df["project_name"] = task_df["project_id"].map(project_path_map).fillna("Sem projeto")
    task_df["root_name"] = task_df["project_id"].map(root_name_map).fillna("Sem projeto")
    task_df["priority"] = pd.to_numeric(task_df["priority"], errors="coerce").fillna(1).astype(int)
    task_df["due_date"] = pd.to_datetime(task_df["due_date"], errors="coerce")
    task_df["created_at_dt"] = _parse_datetime_series(task_df["created_at"])
    task_df["completed_at_dt"] = _parse_datetime_series(task_df["completed_at"])
    task_df["due_day"] = task_df["due_date"].dt.date
    task_df["created_day"] = task_df["created_at_dt"].dt.date
    task_df["completed_day"] = task_df["completed_at_dt"].dt.date
    task_df["priority_label"] = "P" + task_df["priority"].astype(str)
    task_df["labels_text"] = task_df["labels_json"].fillna("[]")
    today = pd.Timestamp(date.today())
    task_df["aging_days"] = (today - task_df["created_at_dt"]).dt.days
    return task_df
