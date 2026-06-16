import sqlite3
from datetime import datetime

class ErrorPatternDB:
    def __init__(self, db_path: str = "hallucination_patterns.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                output TEXT,
                error_type TEXT,
                correction TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_error(self, output: str, error_type: str, correction: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO errors (output, error_type, correction, timestamp) VALUES (?, ?, ?, ?)",
            (output, error_type, correction, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    def check_pattern(self, output: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Find matches by searching for matching error types
        cursor.execute("SELECT error_type, correction, COUNT(*) FROM errors WHERE ? LIKE '%' || output || '%' GROUP BY error_type", (output,))
        patterns = cursor.fetchall()
        conn.close()
        return {
            "known_patterns": patterns,
            "should_prevent": len(patterns) > 0
        }
