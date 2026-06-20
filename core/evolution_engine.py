from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class EvolutionEngine:
    """Persists task outcomes, detects repeated failures, and proposes new skills."""

    def __init__(self, db_path: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.getenv("EVOLUTION_DB_PATH", os.path.join(base, "data", "evolution.db"))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    approach TEXT NOT NULL,
                    result TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def learn_from_success(self, task: str, approach: str, result: str) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO task_history (task, approach, result, success, created_at) VALUES (?, ?, ?, ?, ?)",
                (task, approach, result, 1, created_at),
            )
            conn.commit()
            return {"stored": True, "task": task, "approach": approach, "result": result}
        finally:
            conn.close()

    def detect_repeated_failures(self, min_occurrences: int = 3) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT task, COUNT(*) as failures
                FROM task_history
                WHERE success = 0
                GROUP BY task
                HAVING failures >= ?
                """,
                (min_occurrences,),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def propose_new_skill(self, pattern: str) -> Dict[str, Any]:
        skill_name = f"auto_{pattern.strip().replace(' ', '_').lower()}"
        return {
            "skill_name": skill_name,
            "source_pattern": pattern,
            "status": "proposed",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
