from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class EvolutionEngine:
    """Persists task outcomes, detects repeated failures, proposes and auto-generates skills."""

    def __init__(self, db_path: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.getenv("EVOLUTION_DB_PATH", os.path.join(base, "data", "evolution.db"))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    approach TEXT NOT NULL,
                    result TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prompt_optimizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_hash TEXT NOT NULL,
                    original_prompt TEXT,
                    optimized_prompt TEXT,
                    improvement REAL,
                    applied INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skill_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    source_pattern TEXT,
                    generated_code TEXT,
                    status TEXT DEFAULT 'proposed',
                    created_at TEXT NOT NULL,
                    registered_at TEXT
                );
                CREATE TABLE IF NOT EXISTS feedback_loop (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    query TEXT,
                    retrieved_chunks TEXT,
                    user_rating REAL,
                    adjusted INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
            """)
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

    def learn_from_failure(self, task: str, approach: str, result: str) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO task_history (task, approach, result, success, created_at) VALUES (?, ?, ?, ?, ?)",
                (task, approach, result, 0, created_at),
            )
            conn.commit()
            return {"stored": True, "task": task, "approach": approach, "result": result}
        finally:
            conn.close()

    def detect_repeated_failures(self, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT task, approach, COUNT(*) as failures, MAX(created_at) as last_failed
                FROM task_history
                WHERE success = 0
                GROUP BY task, approach
                HAVING failures >= ?
                ORDER BY failures DESC
                """,
                (min_occurrences,),
            )
            return [
                {"task": row[0], "approach": row[1], "failures": row[2], "last_failed": row[3]}
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def propose_new_skill(self, pattern: str) -> Dict[str, Any]:
        skill_name = f"auto_{pattern.strip().replace(' ', '_').lower()}"
        created_at = datetime.now(timezone.utc).isoformat()
        code = (
            f"class {''.join(part.capitalize() for part in skill_name.split('_'))}:\n"
            f"    def __init__(self): ...\n"
            f"    def run(self, payload: dict) -> dict:\n"
            f"        return {{'skill': '{skill_name}', 'status': 'ok'}}\n"
        )
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO skill_proposals (skill_name, source_pattern, generated_code, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (skill_name, pattern, code, "proposed", created_at),
            )
            conn.commit()
            return {
                "skill_name": skill_name,
                "source_pattern": pattern,
                "status": "proposed",
                "generated_code": code,
                "generated_at": created_at,
            }
        finally:
            conn.close()

    def record_feedback(self, session_id: str, query: str, retrieved_chunks: str, user_rating: float) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO feedback_loop (session_id, query, retrieved_chunks, user_rating, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, query, retrieved_chunks, user_rating, created_at),
            )
            conn.commit()
            return {"recorded": True, "session_id": session_id, "rating": user_rating}
        finally:
            conn.close()

    def run_daily_evolution(self, task_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(task_history)
        successful = sum(1 for t in task_history if t.get("success"))
        success_rate = (successful / total * 100.0) if total > 0 else 100.0
        failures = self.detect_repeated_failures()
        failed_tasks = [f["task"] for f in failures]
        new_skills = []
        for task in failed_tasks:
            proposal = self.propose_new_skill(task)
            new_skills.append(proposal["skill_name"])
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tasks_processed": total,
            "success_rate": success_rate,
            "repeated_failures": len(failures),
            "optimizations": [
                "Increase RAG context depth to reduce hallucination."
            ] if success_rate < 95 else [],
            "new_skills_proposed": new_skills,
        }
        return report
