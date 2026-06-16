import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from google.cloud import firestore  # type: ignore[import-untyped]
    FIRESTORE_AVAILABLE = True
except Exception:
    FIRESTORE_AVAILABLE = False


class GCPFirestoreVerificationQueue:
    """Firestore-backed verification queue with SQLite local fallback."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        project_id: Optional[str] = None,
        db_path: Optional[str] = None,
        credentials: Any = None,
    ):
        self.collection_name = collection_name or os.getenv("GCP_FIRESTORE_COLLECTION", "verification_queue")
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.client = None
        self.mode = "local_sqlite"
        self.db_path = db_path or os.getenv("GCP_FIRESTORE_SQLITE_PATH")
        self._memory_conn = None

        if FIRESTORE_AVAILABLE and self.project_id:
            try:
                if credentials:
                    self.client = firestore.Client(project=self.project_id, credentials=credentials)
                else:
                    self.client = firestore.Client(project=self.project_id)
                self.mode = "gcp_firestore"
                logger.info("Using GCP Firestore verification queue")
            except Exception as exc:
                logger.warning(f"Firestore unavailable, falling back to SQLite: {exc}")

        if self.mode == "local_sqlite":
            if not self.db_path:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self.db_path = os.path.join(base_dir, "data", "gcp_firestore_queue.db")
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
                CREATE TABLE IF NOT EXISTS verification_queue (
                    queue_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 50,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    verified_at TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_verification_status ON verification_queue(status, priority)")
            conn.commit()
        finally:
            if self.db_path != ":memory:":
                conn.close()

    def _get_connection(self):
        if self.db_path == ":memory:":
            return self._memory_conn
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def enqueue(
        self,
        task_id: str,
        payload: Dict[str, Any],
        priority: int = 50,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = self._now()
        document = {
            "task_id": task_id,
            "payload": payload,
            "priority": int(priority),
            "metadata": metadata or {},
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }

        if self.client is not None:
            _, ref = self.client.collection(self.collection_name).add(document)
            return {
                "success": True,
                "provider": "gcp_firestore",
                "queue_id": ref.id,
                "task_id": task_id,
                "status": "pending",
            }

        queue_id = uuid.uuid4().hex
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO verification_queue
                (queue_id, task_id, payload, priority, metadata, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    queue_id,
                    task_id,
                    json.dumps(payload, default=str),
                    int(priority),
                    json.dumps(metadata or {}, default=str),
                    now,
                    now,
                ),
            )
            conn.commit()
        return {
            "success": True,
            "provider": "local_sqlite",
            "queue_id": queue_id,
            "task_id": task_id,
            "status": "pending",
        }

    def get_pending(self, limit: int = 10) -> List[Dict[str, Any]]:
        if self.client is not None:
            rows = (
                self.client.collection(self.collection_name)
                .where("status", "==", "pending")
                .order_by("priority", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            return [self._firestore_doc_to_dict(row) for row in rows]

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT queue_id, task_id, payload, priority, metadata, status, created_at, updated_at, verified_at
                FROM verification_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def peek(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.get_pending(limit=limit)

    def mark_verified(self, task_id: str) -> Dict[str, Any]:
        now = self._now()
        if self.client is not None:
            query = (
                self.client.collection(self.collection_name)
                .where("task_id", "==", task_id)
                .where("status", "==", "pending")
                .limit(1)
            )
            updated = 0
            for doc in query.stream():
                doc.reference.update({"status": "verified", "updated_at": now, "verified_at": now})
                updated += 1
            return {"success": True, "provider": "gcp_firestore", "task_id": task_id, "verified": updated}

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE verification_queue
                SET status = 'verified', updated_at = ?, verified_at = ?
                WHERE task_id = ? AND status = 'pending'
                """,
                (now, now, task_id),
            )
            conn.commit()
        return {"success": True, "provider": "local_sqlite", "task_id": task_id, "verified": cursor.rowcount}

    def delete(self, queue_id: str) -> Dict[str, Any]:
        if self.client is not None:
            doc = self.client.collection(self.collection_name).document(queue_id)
            doc.delete()
            return {"success": True, "provider": "gcp_firestore", "queue_id": queue_id, "deleted": True}

        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM verification_queue WHERE queue_id = ?", (queue_id,))
            conn.commit()
        return {"success": True, "provider": "local_sqlite", "queue_id": queue_id, "deleted": cursor.rowcount > 0}

    def stats(self) -> Dict[str, Any]:
        if self.client is not None:
            pending = len(list(self.client.collection(self.collection_name).where("status", "==", "pending").stream()))
            verified = len(list(self.client.collection(self.collection_name).where("status", "==", "verified").stream()))
            return {
                "provider": "gcp_firestore",
                "collection": self.collection_name,
                "pending": pending,
                "verified": verified,
                "total": pending + verified,
            }

        with self._get_connection() as conn:
            pending = conn.execute("SELECT COUNT(*) FROM verification_queue WHERE status = 'pending'").fetchone()[0]
            verified = conn.execute("SELECT COUNT(*) FROM verification_queue WHERE status = 'verified'").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM verification_queue").fetchone()[0]
        return {
            "provider": "local_sqlite",
            "db_path": self.db_path,
            "pending": pending,
            "verified": verified,
            "total": total,
        }

    def close(self) -> None:
        if self.client is not None:
            self.client = None
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None

    def _firestore_doc_to_dict(self, doc: Any) -> Dict[str, Any]:
        data = doc.to_dict()
        data["queue_id"] = doc.id
        return data

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "queue_id": row["queue_id"],
            "task_id": row["task_id"],
            "payload": json.loads(row["payload"]),
            "priority": row["priority"],
            "metadata": json.loads(row["metadata"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "verified_at": row["verified_at"],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
