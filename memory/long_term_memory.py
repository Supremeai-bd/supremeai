from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger


class LongTermMemory:
    def __init__(
        self,
        db_path: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.path.join(base_dir, "data", "long_term_memory.db")
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.session_id = session_id or "default"
        self._memory_conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            return self._memory_conn
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 1.0,
                    source TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    turn_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_facts_session ON facts(session_id, category)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_session ON conversation_summaries(session_id)"
            )
            conn.commit()
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def remember_fact(
        self,
        content: str,
        category: str = "general",
        importance: float = 1.0,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = self._now()
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                INSERT INTO facts (session_id, category, content, importance, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (self.session_id, category, content, importance, source, now, now),
            )
            conn.commit()
            return {"status": "ok", "fact_id": cursor.lastrowid}
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def recall_facts(
        self,
        category: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM facts WHERE session_id = ? AND importance >= ?"
            params: List[Any] = [self.session_id, min_importance]
            if category:
                query += " AND category = ?"
                params.append(category)
            query += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def save_summary(self, summary: str, turn_count: int) -> Dict[str, Any]:
        now = self._now()
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                INSERT INTO conversation_summaries (session_id, summary, turn_count, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (self.session_id, summary, turn_count, now),
            )
            conn.commit()
            return {"status": "ok", "summary_id": cursor.lastrowid}
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def get_recent_summaries(self, limit: int = 5) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM conversation_summaries
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (self.session_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def build_context(self, limit: int = 10) -> str:
        facts = self.recall_facts(limit=limit)
        summaries = self.get_recent_summaries(limit=3)
        parts: List[str] = []
        if summaries:
            parts.append("Recent conversation summaries:")
            for item in summaries:
                parts.append(f"- {item['summary']}")
        if facts:
            parts.append("Known facts:")
            for item in facts:
                parts.append(f"- [{item['category']}] {item['content']}")
        return "\n".join(parts)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
