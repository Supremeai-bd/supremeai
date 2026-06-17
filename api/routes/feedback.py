from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

DB_PATH = Path("data/feedback.db")


def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackEvent(BaseModel):
    event_type: str
    payload: Optional[Dict[str, Any]] = None


class FeedbackResponse(BaseModel):
    success: bool
    event_id: Optional[int] = None


@router.on_event("startup")
def _startup() -> None:
    _ensure_db()


@router.post("/ingest", response_model=FeedbackResponse)
async def ingest(event: FeedbackEvent) -> FeedbackResponse:
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.execute(
            "INSERT INTO feedback_events (event_type, payload, created_at) VALUES (?, ?, ?)",
            (event.event_type, __import__("json").dumps(event.payload or {}), time.time()),
        )
        conn.commit()
        conn.close()
        return FeedbackResponse(success=True, event_id=cursor.lastrowid)
    except Exception as exc:
        logger.error(f"feedback ingest failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
