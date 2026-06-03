from datetime import date

from src.analytics import compute_task_score, compute_metrics


def test_compute_task_score_penalizes_overdue_tasks():
    task = {
        "due_date": "2026-06-01",
        "priority": 4,
        "status": "open",
    }
    score, reason = compute_task_score(task, "Projeto X", today=date(2026, 6, 3))
    assert score > 0
    assert "atraso" in reason


def test_compute_metrics_counts_open_tasks():
    tasks = [
        {"status": "open", "due_date": None, "created_at": "2026-06-02T10:00:00Z", "completed_at": None},
        {"status": "completed", "due_date": None, "created_at": "2026-06-01T10:00:00Z", "completed_at": "2026-06-03T09:00:00Z"},
    ]
    projects = []
    metrics = compute_metrics(tasks, projects)
    assert metrics["open_tasks"] == 1
