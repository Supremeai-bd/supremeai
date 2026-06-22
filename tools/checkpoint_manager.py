import os, json, sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from loguru import logger

@dataclass
class Checkpoint:
    task_id: str
    step_index: int
    state: Dict[str, Any]
    created_at: str
    resumed: bool = False

class CheckpointManager:
    """Persists task execution state to allow long runs to pause and resume."""
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "data", "checkpoints.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    task_id TEXT PRIMARY KEY,
                    step_index INTEGER,
                    state TEXT,
                    created_at TEXT,
                    resumed INTEGER DEFAULT 0
                )
            """)

    def save(self, task_id: str, step_index: int, state: Dict[str, Any]) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO checkpoints (task_id, step_index, state, created_at, resumed) VALUES (?, ?, ?, ?, COALESCE((SELECT resumed FROM checkpoints WHERE task_id = ?), 0))",
                    (task_id, step_index, json.dumps(state), datetime.now(timezone.utc).isoformat(), task_id),
                )
            logger.info(f"Checkpoint saved for task_id={task_id} step={step_index}")
            return True
        except Exception as exc:
            logger.error(f"Failed to save checkpoint: {exc}")
            return False

    def load(self, task_id: str) -> Optional[Checkpoint]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT task_id, step_index, state, created_at, resumed FROM checkpoints WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            cp = Checkpoint(task_id=row[0], step_index=row[1], state=json.loads(row[2]), created_at=row[3], resumed=bool(row[4]))
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE checkpoints SET resumed = 1 WHERE task_id = ?", (task_id,))
            return cp
        except Exception as exc:
            logger.error(f"Failed to load checkpoint: {exc}")
            return None

    def list_all(self) -> List[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("SELECT task_id, step_index, created_at, resumed FROM checkpoints ORDER BY created_at DESC").fetchall()
            return [{"task_id": r[0], "step_index": r[1], "created_at": r[2], "resumed": bool(r[3])} for r in rows]
        except Exception as exc:
            logger.error(f"Failed to list checkpoints: {exc}")
            return []

    def clear(self, task_id: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM checkpoints WHERE task_id = ?", (task_id,))
            return True
        except Exception as exc:
            logger.error(f"Failed to clear checkpoint: {exc}")
            return False
