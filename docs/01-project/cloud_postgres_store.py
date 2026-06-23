"""
Cloud-native PostgreSQL store using Supabase/Cloud SQL.
Replaces local SQLite for production.
"""
import os
from typing import Dict, Any, Optional, List
from loguru import logger
import psycopg2
from psycopg2.extras import RealDictCursor

class CloudPostgresStore:
    """
    Production-grade PostgreSQL store.
    Uses Supabase or Cloud SQL connection string.
    """

    def __init__(self):
        self.conn_string = os.getenv(
            "DATABASE_URL",
            os.getenv("SUPABASE_DATABASE_URL", "")
        )
        self._init_tables()

    def _get_conn(self):
        return psycopg2.connect(self.conn_string, cursor_factory=RealDictCursor)

    def _init_tables(self):
        """Initialize tables if not exist."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS task_history (
                        id SERIAL PRIMARY KEY,
                        task_type VARCHAR(50),
                        prompt TEXT,
                        result TEXT,
                        provider VARCHAR(100),
                        cost DECIMAL(10,6),
                        latency_ms INTEGER,
                        success BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_context (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100),
                        user_id VARCHAR(100),
                        messages JSONB,
                        summary TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS verification_queue (
                        id SERIAL PRIMARY KEY,
                        email_target VARCHAR(255),
                        otp_code VARCHAR(20),
                        verification_link TEXT,
                        processed BOOLEAN DEFAULT false,
                        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info("PostgreSQL tables initialized")

    def save_task(self, task_data: Dict[str, Any]) -> int:
        """Save task execution record."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO task_history 
                    (task_type, prompt, result, provider, cost, latency_ms, success)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    task_data.get("task_type"),
                    task_data.get("prompt"),
                    task_data.get("result"),
                    task_data.get("provider"),
                    task_data.get("cost", 0.0),
                    task_data.get("latency_ms", 0),
                    task_data.get("success", True)
                ))
                result = cur.fetchone()
                conn.commit()
                return result["id"]

    def get_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation context by session."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM conversation_context 
                    WHERE session_id = %s 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """, (session_id,))
                result = cur.fetchone()
                return dict(result) if result else None

    def update_conversation(self, session_id: str, messages: List[Dict], summary: str = ""):
        """Update or create conversation context."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO conversation_context (session_id, messages, summary)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        messages = EXCLUDED.messages,
                        summary = EXCLUDED.summary,
                        updated_at = CURRENT_TIMESTAMP
                """, (session_id, Json(messages), summary))
                conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_tasks,
                        AVG(cost) as avg_cost,
                        SUM(cost) as total_cost,
                        AVG(latency_ms) as avg_latency,
                        COUNT(CASE WHEN success THEN 1 END)::FLOAT / COUNT(*) * 100 as success_rate
                    FROM task_history
                """)
                result = cur.fetchone()
                return dict(result) if result else {}

# Keep SQLite fallback for local dev
class SQLiteStore:
    """Local SQLite store for development only."""
    def __init__(self, db_path: str = "data/supremeai.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # ... existing SQLite implementation ...
