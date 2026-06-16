import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from google.cloud import pubsub_v1  # type: ignore[import-untyped]
    PUBSUB_AVAILABLE = True
except Exception:
    PUBSUB_AVAILABLE = False


class GCPPubSubQueue:
    """Google Pub/Sub task queue with SQLite local fallback."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.topic_id = topic_id or os.getenv("GCP_PUBSUB_TOPIC", "supremeai-tasks")
        self.subscription_id = subscription_id or os.getenv("GCP_PUBSUB_SUBSCRIPTION") or f"{self.topic_id}-sub"
        self.db_path = db_path or os.getenv("GCP_PUBSUB_SQLITE_PATH")
        self.publisher = None
        self.subscriber = None
        self.mode = "local_sqlite"
        self._memory_conn = None

        if PUBSUB_AVAILABLE and self.project_id:
            try:
                self.publisher = pubsub_v1.PublisherClient()
                self.subscriber = pubsub_v1.SubscriberClient()
                self.topic_path = self.publisher.topic_path(self.project_id, self.topic_id)
                self.subscription_path = self.subscriber.subscription_path(self.project_id, self.subscription_id)
                self.mode = "gcp_pubsub"
                logger.info("Using GCP Pub/Sub task queue")
            except Exception as exc:
                logger.warning(f"Pub/Sub unavailable, falling back to SQLite: {exc}")

        if self.mode == "local_sqlite":
            if not self.db_path:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self.db_path = os.path.join(base_dir, "data", "gcp_pubsub_queue.db")
            if self.db_path != ":memory:":
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._init_db()

    @property
    def provider(self) -> str:
        return self.mode

    def _init_db(self) -> None:
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn = self._memory_conn
        else:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)

        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pubsub_queue (
                    message_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    acked INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pubsub_acked ON pubsub_queue(acked)")
            conn.commit()
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def _get_connection(self):
        if self.db_path == ":memory:":
            return self._memory_conn
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def publish(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = self._now()
        if self.publisher is not None:
            data = json.dumps(
                {
                    "task_id": task_id,
                    "payload": payload,
                    "published_at": now,
                },
                default=str,
            ).encode("utf-8")
            future = self.publisher.publish(self.topic_path, data=data)
            message_id = future.result(timeout=10)
            return {
                "success": True,
                "provider": "gcp_pubsub",
                "topic": self.topic_id,
                "message_id": message_id,
                "task_id": task_id,
            }

        message_id = uuid.uuid4().hex
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pubsub_queue (message_id, task_id, payload, published_at, acked)
                VALUES (?, ?, ?, ?, 0)
                """,
                (message_id, task_id, json.dumps(payload, default=str), now),
            )
            conn.commit()
        return {
            "success": True,
            "provider": "local_sqlite",
            "topic": self.topic_id,
            "message_id": message_id,
            "task_id": task_id,
        }

    def pull(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        if self.subscriber is not None:
            response = self.subscriber.pull(
                request={
                    "subscription": self.subscription_path,
                    "max_messages": max_messages,
                }
            )
            messages = []
            for received in response.received_messages:
                data = json.loads(received.message.data.decode("utf-8"))
                messages.append(
                    {
                        "message_id": received.ack_id,
                        "task_id": data.get("task_id"),
                        "payload": data.get("payload"),
                        "attributes": dict(received.message.attributes),
                        "published_at": data.get("published_at"),
                    }
                )
            return messages

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT message_id, task_id, payload, published_at
                FROM pubsub_queue
                WHERE acked = 0
                ORDER BY published_at ASC
                LIMIT ?
                """,
                (max_messages,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def ack(self, message_id: str) -> Dict[str, Any]:
        if self.subscriber is not None:
            self.subscriber.acknowledge(self.subscription_path, [message_id])
            return {"success": True, "provider": "gcp_pubsub", "message_id": message_id, "acked": True}

        with self._get_connection() as conn:
            cursor = conn.execute("UPDATE pubsub_queue SET acked = 1 WHERE message_id = ?", (message_id,))
            conn.commit()
        return {"success": True, "provider": "local_sqlite", "message_id": message_id, "acked": cursor.rowcount > 0}

    def stats(self) -> Dict[str, Any]:
        if self.subscriber is not None:
            return {
                "provider": "gcp_pubsub",
                "topic": self.topic_id,
                "subscription": self.subscription_id,
                "pending": None,
                "acked": None,
            }

        with self._get_connection() as conn:
            pending = conn.execute("SELECT COUNT(*) FROM pubsub_queue WHERE acked = 0").fetchone()[0]
            acked = conn.execute("SELECT COUNT(*) FROM pubsub_queue WHERE acked = 1").fetchone()[0]
        return {
            "provider": "local_sqlite",
            "db_path": self.db_path,
            "topic": self.topic_id,
            "subscription": self.subscription_id,
            "pending": pending,
            "acked": acked,
            "total": pending + acked,
        }

    def close(self) -> None:
        if self.publisher is not None:
            self.publisher.transport.close()
        if self.subscriber is not None:
            self.subscriber.transport.close()
        self.publisher = None
        self.subscriber = None
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "message_id": row["message_id"],
            "task_id": row["task_id"],
            "payload": json.loads(row["payload"]),
            "published_at": row["published_at"],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
