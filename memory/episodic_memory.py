#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> episodic_memory.py
# project >> SupremeAI 2.0
# purpose >> Memory storage
# module >> memory
# ============================================================================
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional



class EpisodicMemory:
    def __init__(
        self,
        db_path: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.path.join(base_dir, "data", "episodic_memory.db")
        self.session_id = session_id or "default"
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
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
        is_memory = self.db_path == ":memory:"
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    context TEXT NOT NULL,
                    outcome TEXT,
                    importance REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id, event_type)"
            )
            conn.commit()
        finally:
            if not is_memory:
                conn.close()

    def _with_connection(self, func):
        conn = self._connect()
        is_memory = self.db_path == ":memory:"
        try:
            return func(conn)
        finally:
            if not is_memory:
                conn.close()

    def store_episode(
        self,
        event_type: str,
        context: str,
        outcome: Optional[str] = None,
        importance: float = 1.0,
    ) -> Dict[str, Any]:
        now = self._now()

        def _insert(conn: sqlite3.Connection) -> Dict[str, Any]:
            cursor = conn.execute(
                """
                INSERT INTO episodes (session_id, event_type, context, outcome, importance, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self.session_id, event_type, context, outcome, importance, now),
            )
            conn.commit()
            return {"status": "ok", "episode_id": cursor.lastrowid}

        return self._with_connection(_insert)

    def recall_episodes(
        self,
        event_type: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        def _query(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM episodes WHERE session_id = ? AND importance >= ?"
            params: List[Any] = [self.session_id, min_importance]
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            query += " ORDER BY importance DESC, created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

        return self._with_connection(_query)

    def summarize_recent(self, limit: int = 5) -> str:
        episodes = self.recall_episodes(limit=limit)
        if not episodes:
            return ""
        lines = ["Recent episodes:"]
        for ep in episodes:
            lines.append(f"- [{ep['event_type']}] {ep['context']}")
        return "\n".join(lines)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
