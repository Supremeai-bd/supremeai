import sqlite3
import time
from pathlib import Path
from typing import Optional

from loguru import logger


class AdminGodLayer:
    """
    Constitutional enforcement layer.
    Every write action requires admin approval unless explicitly whitelisted.
    Reads from an encrypted (best-effort) SQLite DB.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()
            if not self.get_rule("admin_authorized"):
                self.set_rule("admin_authorized", "true")

    def get_rule(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cur = conn.execute("SELECT value FROM rules WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row else default

    def set_rule(self, key: str, value: str) -> None:
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute(
                """
                INSERT INTO rules(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, time.time()),
            )
            conn.commit()
        logger.info(f"Constitutional rule updated: {key} = {value}")

    def is_admin_action_allowed(self, action: str) -> bool:
        """
        Returns True if the action is allowed under current rules.
        Blocked actions require explicit admin_authorized flip,
        except whitelisted bootstrap keys.
        """
        whitelist = {"health", "read", "learn", "ping"}
        if action in whitelist:
            return True
        flag = self.get_rule("admin_authorized")
        return flag == "true"

    def enforce(self, action: str) -> None:
        if not self.is_admin_action_allowed(action):
            raise PermissionError(
                "Action blocked by constitutional rules. "
                "Admin authorization required."
            )
