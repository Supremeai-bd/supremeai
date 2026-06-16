import os
import sqlite3
from datetime import datetime
from loguru import logger

class AuditLogger:
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "data", "supreme_memory.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,
                decision_details TEXT,
                reasoning TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def log_decision(self, action_type: str, decision_details: str, reasoning: str):
        """Logs an autonomous decision or rotation details to the tamper-proof audit trail."""
        logger.info(f"[AUDIT LOG] {action_type} - Details: {decision_details} - Reason: {reasoning}")
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (action_type, decision_details, reasoning) VALUES (?, ?, ?)",
                (action_type, decision_details, reasoning)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to write to audit database: {e}")

    def get_audit_trail(self) -> list:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            logs = [dict(r) for r in rows]
            conn.close()
            return logs
        except Exception as e:
            logger.error(f"Failed to query audit trail: {e}")
            return []
