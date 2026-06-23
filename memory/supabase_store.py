from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from memory.sqlite_store import SQLiteMemoryStore


class SupabaseStore(SQLiteMemoryStore):
    def __init__(self, database_url: Optional[str] = None, local_path: Optional[str] = None):
        self.database_url = database_url or os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
        self.local_path = local_path or os.getenv("SQLITE_PATH", "data/supremeai.db")
        self._provider = "supabase" if self.database_url else "sqlite"
        self._supabase_client = None
        super().__init__(self.local_path)

    @property
    def provider(self) -> str:
        return self._provider

    def _get_supabase_client(self):
        if self._supabase_client is None:
            try:
                from supabase import create_client
                url = self.database_url.replace("/postgres", "")
                key = os.getenv("SUPABASE_KEY", "")
                self._supabase_client = create_client(url, key)
            except Exception as exc:
                raise RuntimeError(f"Supabase client init failed: {exc}") from exc
        return self._supabase_client

    def save_conversation(self, session_id: str, messages: list) -> None:
        if self._provider == "supabase":
            client = self._get_supabase_client()
            client.table("conversations").upsert({
                "session_id": session_id,
                "messages": json.dumps(messages),
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()
        else:
            rows = self.get_session_messages(session_id)
            for msg in messages:
                if isinstance(msg, dict):
                    self.save_message(session_id, msg.get("role", "user"), msg.get("content", ""))

    def get_conversation(self, session_id: str) -> list:
        if self._provider == "supabase":
            client = self._get_supabase_client()
            result = client.table("conversations").select("messages").eq("session_id", session_id).execute()
            rows = result.data
            if rows:
                return json.loads(rows[0]["messages"])
            return []
        return self.get_session_messages(session_id)

    def save_learned_fact(self, fact: dict) -> None:
        fact_id = fact.get("id")
        if not fact_id:
            fact_id = f"fact_{datetime.utcnow().timestamp()}"
            fact["id"] = fact_id
        fact["created_at"] = fact.get("created_at", datetime.utcnow().isoformat())
        if self._provider == "supabase":
            client = self._get_supabase_client()
            client.table("learned_facts").upsert({
                "id": fact_id,
                "content": json.dumps(fact),
                "tags": json.dumps(fact.get("tags", [])),
                "created_at": fact["created_at"],
            }).execute()
        else:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO tasks (id, task_description, task_type, success, cost, outcome_text) VALUES (?, ?, ?, ?, ?, ?)",
                (fact_id, json.dumps(fact), "learned_fact", 1, 0.0, json.dumps(fact)),
            )
            conn.commit()
            self._close_connection(conn)

    def search_facts(self, query: str) -> list:
        if self._provider == "supabase":
            client = self._get_supabase_client()
            result = client.table("learned_facts").select("content").ilike("content", f"%{query}%").execute()
            return [json.loads(row["content"]) for row in result.data]
        return []
