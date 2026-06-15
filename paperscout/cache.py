"""SQLite cache of HTTP responses, keyed by a caller-supplied key."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional


class Cache:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS responses "
            "(key TEXT PRIMARY KEY, body TEXT NOT NULL, fetched_at REAL NOT NULL)"
        )
        self.conn.commit()

    def get(self, key: str, max_age_seconds: Optional[float]) -> Optional[str]:
        row = self.conn.execute(
            "SELECT body, fetched_at FROM responses WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        body, fetched_at = row
        if max_age_seconds is not None and (time.time() - fetched_at) > max_age_seconds:
            return None
        return body

    def put(self, key: str, body: str) -> None:
        self.conn.execute(
            "INSERT INTO responses (key, body, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET body=excluded.body, fetched_at=excluded.fetched_at",
            (key, body, time.time()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
