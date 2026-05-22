# src/activity_finder/cache.py
"""SQLite cache for scanned app info."""

import json
import sqlite3
import time


class AppCache:
    def __init__(self, db_path: str = "apps.db"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_cache (
                package_name TEXT PRIMARY KEY,
                labels TEXT,
                launch_activity TEXT,
                updated_at REAL
            )
            """
        )
        self._conn.commit()

    def get(self, package_name: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM app_cache WHERE package_name = ?", (package_name,)
        ).fetchone()
        return dict(row) if row else None

    def put(self, package_name: str, labels: list[str], activity: str) -> None:
        self._conn.execute(
            """
            INSERT INTO app_cache (package_name, labels, launch_activity, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(package_name) DO UPDATE SET
                labels = excluded.labels,
                launch_activity = excluded.launch_activity,
                updated_at = excluded.updated_at
            """,
            (package_name, json.dumps(labels, ensure_ascii=False), activity, time.time()),
        )
        self._conn.commit()

    def is_stale(self, package_name: str, ttl_seconds: int = 86400) -> bool:
        row = self.get(package_name)
        if row is None:
            return True
        return (time.time() - row["updated_at"]) > ttl_seconds

    def find_by_label(self, label_keyword: str) -> list[dict]:
        """Search cache for entries whose labels contain the keyword (substring match)."""
        results = []
        rows = self._conn.execute("SELECT * FROM app_cache").fetchall()
        for row in rows:
            labels = json.loads(row["labels"])
            for label in labels:
                if label_keyword in label:
                    results.append({
                        "package_name": row["package_name"],
                        "launch_activity": row["launch_activity"],
                        "label": label,
                    })
                    break
        return results

    def close(self) -> None:
        self._conn.close()
