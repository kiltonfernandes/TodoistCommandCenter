from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    todoist_api_token: str | None
    database_path: Path


def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[1]
    db_path = Path(os.getenv("TCC_DB_PATH", base_dir / "todoist_command_center.sqlite3"))
    token = os.getenv("TODOIST_API_TOKEN")
    return Settings(todoist_api_token=token, database_path=db_path)
