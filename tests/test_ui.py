from __future__ import annotations

from src.dataframes import prepare_task_frame


def test_prepare_task_frame_tolerates_missing_project_id():
    frame = prepare_task_frame([{"task_id": "t1", "content": "Loose task"}], {})

    assert "project_id" in frame.columns
    assert frame.loc[0, "project_name"] == "Sem projeto"


def test_prepare_task_frame_handles_timezone_aware_created_at():
    frame = prepare_task_frame(
        [{"task_id": "t1", "content": "Task", "created_at": "2026-06-01T10:00:00Z"}],
        {},
    )

    assert "aging_days" in frame.columns
