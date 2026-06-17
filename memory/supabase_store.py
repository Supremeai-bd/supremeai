from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from memory.sqlite_store import SQLiteStore


class SupabaseStore(SQLiteStore):
    def __init__(self, database_url: Optional[str] = None, local_path: Optional[str] = None):
        self.database_url = database_url or os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
        self.local_path = local_path or os.getenv("SQLITE_PATH", "data/supremeai.db")
        self._provider = "supabase" if self.database_url else "sqlite"
        super().__init__(self.local_path)

    @property
    def provider(self) -> str:
        return self._provider

    def connect(self) -> None:
        if self._provider == "supabase" and self.database_url:
            try:
                import psycopg  # type: ignore
                self._conn = psycopg.connect(self.database_url)
                self._provider = "supabase"
                return
            except Exception as exc:
                raise RuntimeError(f"Supabase connection failed: {exc}") from exc
        super().connect()
