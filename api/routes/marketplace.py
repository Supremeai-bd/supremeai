from __future__ import annotations

import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from loguru import logger

router = APIRouter(prefix="/api/skills", tags=["skills"])

DB_PATH = os.environ.get("SUPREMEAI_MARKETPLACE_DB", "data/marketplace.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            description TEXT,
            dependencies TEXT,
            installed INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'builtin',
            installed_at REAL
        )
        """
    )
    conn.commit()
    return conn


def _row_to_skill(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "version": row["version"],
        "description": row["description"],
        "dependencies": row["dependencies"],
        "installed": bool(row["installed"]),
        "source": row["source"],
        "installed_at": row["installed_at"],
    }


_seeded = False
_SEED_INDEX = [
    {
        "name": "web_scraper",
        "version": "1.0.0",
        "description": "Scrapes website contents using BeautifulSoup.",
        "dependencies": "beautifulsoup4, requests",
        "source": "builtin",
    },
    {
        "name": "csv_exporter",
        "version": "1.0.0",
        "description": "Exports tabular data to CSV using pandas.",
        "dependencies": "pandas",
        "source": "builtin",
    },
]


def _seed(conn: sqlite3.Connection) -> None:
    global _seeded
    if _seeded:
        return
    row = conn.execute("SELECT COUNT(*) AS c FROM skills").fetchone()
    if row["c"] > 0:
        _seeded = True
        return
    now = os.path.getctime(DB_PATH) if os.path.exists(DB_PATH) else 0
    for item in _SEED_INDEX:
        conn.execute(
            "INSERT INTO skills (id, name, version, description, dependencies, installed, source, installed_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (
                str(uuid.uuid4()),
                item["name"],
                item["version"],
                item["description"],
                item["dependencies"],
                item["source"],
                now,
            ),
        )
    conn.commit()
    _seeded = True


class SearchRequest(BaseModel):
    query: str
    installed_only: bool = False


class SkillResponse(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str]
    dependencies: Optional[str]
    installed: bool
    source: str


class InstallRequest(BaseModel):
    skill: str
    version: Optional[str] = None


@router.post("/search", response_model=List[SkillResponse])
def search_skills(req: SearchRequest) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        _seed(conn)
        sql = "SELECT id, name, version, description, dependencies, installed, source FROM skills WHERE (name LIKE ? OR description LIKE ?)"
        like = f"%{req.query}%"
        params: List[Any] = [like, like]
        if req.installed_only:
            sql += " AND installed = 1"
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_skill(r) for r in rows]
    except Exception as exc:
        logger.error(f"Marketplace search failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@router.post("/install", response_model=Dict[str, Any])
async def install_skill(req: InstallRequest) -> Dict[str, Any]:
    conn = _get_conn()
    try:
        _seed(conn)
        row = conn.execute(
            "SELECT id, name, installed FROM skills WHERE name = ?",
            (req.skill,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Skill '{req.skill}' not found.")
        if row["installed"]:
            return {"success": True, "skill": req.skill, "installed": True, "message": "Already installed."}
        conn.execute(
            "UPDATE skills SET installed = 1, installed_at = ? WHERE id = ?",
            (__import__("time").time(), row["id"]),
        )
        conn.commit()
        return {"success": True, "skill": req.skill, "installed": True, "message": "Installed."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Skill install failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()
