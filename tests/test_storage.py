from __future__ import annotations

from src.storage import Database


def test_database_fetches_dict_rows(tmp_path):
    db = Database(tmp_path / "tcc.sqlite3")
    db.upsert_projects([{"id": "p1", "name": "Salesforce"}])
    db.replace_tasks([{"id": "t1", "content": "Follow up", "project_id": "p1", "priority": 4}])

    projects = db.fetch_projects()
    tasks = db.fetch_tasks()

    assert projects[0]["project_id"] == "p1"
    assert tasks[0]["project_id"] == "p1"
    assert isinstance(tasks[0], dict)
