from __future__ import annotations

from src.todoist_client import TodoistClient


def test_fetch_all_handles_paginated_api(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append((url, params))
        if params and params.get("cursor") == "abc":
            return FakeResponse({"results": [{"id": "2"}], "next_cursor": None})
        return FakeResponse({"results": [{"id": "1"}], "next_cursor": "abc"})

    monkeypatch.setattr("src.todoist_client.requests.get", fake_get)

    client = TodoistClient("token")
    results = client.fetch_projects()

    assert results == [{"id": "1"}, {"id": "2"}]
    assert calls[0][0].endswith("/projects")
