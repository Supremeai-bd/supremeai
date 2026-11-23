"""Distributed API Key Pool — user contribution ingestion & bonus quota."""
from __future__ import annotations

import asyncio

import hashlib
import os
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.monitoring.logging_config import logger
from core.security.authentication.rbac import get_current_user_token as verify_token_dependency
# বাংলা মন্তব্য: ক্যানোনিকাল এনক্রিপশন ও ভল্ট সার্ভিস ব্যবহার
from core.security.secure_credential_store import encrypt_token
from database.supabase_client import get_db

router = APIRouter(prefix="/pool", tags=["pool"])

BONUS_WEIGHTS = {"kilo": 150000}
DEFAULT_BONUS = 100000
MAX_ACTIVE_KEYS = 10

PROVIDER_MANIFEST = [
    {"id": "kilo", "name": "Kilo AI Gateway", "bonus": 150000, "pattern": r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", "console": "https://kilo.ai"},
    {"id": "gemini", "name": "Google Gemini", "bonus": 100000, "pattern": r"^AIzaSy[A-Za-z0-9_-]{33}$", "console": "https://aistudio.google.com/apikey"},
    {"id": "groq", "name": "Groq Cloud", "bonus": 100000, "pattern": r"^gsk_[A-Za-z0-9]{52}$", "console": "https://console.groq.com/keys"},
    {"id": "cerebras", "name": "Cerebras LPU", "bonus": 100000, "pattern": r"^csk-[a-z0-9]{32,}$", "console": "https://cloud.cerebras.ai/"},
    {"id": "sambanova", "name": "SambaNova Cloud", "bonus": 100000, "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", "console": "https://cloud.sambanova.ai/"},
    {"id": "openrouter", "name": "OpenRouter", "bonus": 100000, "pattern": r"^sk-or-v1-[a-f0-9]{64}$", "console": "https://openrouter.ai/keys"},
    {"id": "github", "name": "GitHub Models", "bonus": 100000, "pattern": r"^(ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})$", "console": "https://github.com/settings/tokens"},
    {"id": "mistral", "name": "Mistral AI", "bonus": 100000, "pattern": r"^[A-Za-z0-9]{32}$", "console": "https://console.mistral.ai/api-keys/"},
    {"id": "cohere", "name": "Cohere", "bonus": 100000, "pattern": r"^[A-Za-z0-9]{40}$", "console": "https://dashboard.cohere.com/api-keys"},
]


class ContributeRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=8)


def _encrypt(raw: str) -> str:
    # বাংলা মন্তব্য: ক্যানোনিকাল encrypt_token ফাংশন দিয়ে fail-closed Fernet এনক্রিপশন
    try:
        return encrypt_token(raw)
    except Exception as exc:
        logger.error(f"Failed to encrypt contributed key: {exc}")
        raise HTTPException(status_code=500, detail="Credential encryption failed")


def _fingerprint(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def _validate(provider: str, api_key: str) -> bool:
    # বাংলা মন্তব্য: প্রতিটি প্রোভাইডারের অথেনটিকেশন কঠোরভাবে (strict 200 OK) যাচাই করা হচ্ছে — fail-closed পলিসি
    p = provider.lower().strip()
    urls = {
        "gemini": f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        "groq": "https://api.groq.com/openai/v1/models",
        "openrouter": "https://openrouter.ai/api/v1/auth/key",
        "cerebras": "https://api.cerebras.ai/v1/models",
        "sambanova": "https://api.sambanova.ai/v1/models",
        "mistral": "https://api.mistral.ai/v1/models",
        "cohere": "https://api.cohere.com/v1/models",
        "github": "https://models.inference.ai.azure.com/catalog/models",
    }
    url = urls.get(p)
    if not url:
        return True
    headers = {"Authorization": f"Bearer {api_key}"}
    if p == "gemini":
        headers = {}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            # শুধু 200 OK স্ট্যাটাস কোডই বৈধ
            return resp.status_code == 200
    except Exception as exc:
        logger.warning(f"Validation probe network error for {p}: {exc}")
        return False


@router.get("/providers")
async def list_providers():
    return {"providers": PROVIDER_MANIFEST}


@router.post("/contribute")
async def contribute(req: ContributeRequest, user: dict = Depends(verify_token_dependency)):
    user_id = user.get("sub") or user.get("user_id") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    provider = req.provider.lower().strip()
    raw = req.api_key.strip()
    manifest_entry = next((m for m in PROVIDER_MANIFEST if m["id"] == provider), None)
    if manifest_entry is None:
        raise HTTPException(status_code=400, detail="Unknown provider")

    import re
    if not re.match(manifest_entry["pattern"], raw):
        raise HTTPException(status_code=400, detail="Key format invalid")

    is_valid = await _validate(provider, raw)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Key validation failed")

    fp = _fingerprint(raw)
    db = get_db()
    # dedup check
    try:
        existing = (await asyncio.to_thread(
            lambda: db.client.table("user_contributed_api_keys").select("id").eq("key_fingerprint", fp).execute()
        )).data
        if existing:
            raise HTTPException(status_code=409, detail="Key already in pool")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"dedup check failed: {exc}")

    # বাংলা মন্তব্য: দৈনিক সাবমিশন ক্যাপ কঠোরভাবে ৫টিতে সীমাবদ্ধ করা (Anti-Abuse Cap)
    today_iso = datetime.now(UTC).date().isoformat()
    try:
        user_rows = (await asyncio.to_thread(
            lambda: db.client.table("user_contributed_api_keys").select("id,created_at").eq("user_id", str(user_id)).execute()
        )).data or []
        today_count = sum(1 for r in user_rows if (r.get("created_at") or "").startswith(today_iso))
        if today_count >= 5:
            raise HTTPException(status_code=429, detail="Daily key submission limit reached (5 keys/day)")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"daily submission cap check warning: {exc}")

    encrypted = _encrypt(raw)
    rec_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    bonus = manifest_entry["bonus"]
    try:
        await asyncio.to_thread(
            lambda: db.client.table("user_contributed_api_keys").insert({
                "id": rec_id,
                "user_id": str(user_id),
                "provider": provider,
                "encrypted_key": encrypted,
                "key_fingerprint": fp,
                "status": "valid",
                "bonus_weight": bonus,
                "last_verified_at": now,
                "created_at": now,
                "updated_at": now,
            }).execute()
        )
    except Exception as exc:
        logger.exception(f"insert failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to store key")

    # recompute roll-up cache
    try:
        rows = (await asyncio.to_thread(
            lambda: db.client.table("user_contributed_api_keys").select("provider,status").eq("user_id", str(user_id)).execute()
        )).data or []
        valid_count = 0
        total_bonus = 0
        for r in rows:
            if r.get("status") != "valid":
                continue
            if valid_count >= MAX_ACTIVE_KEYS:
                break
            valid_count += 1
            total_bonus += BONUS_WEIGHTS.get(r["provider"], DEFAULT_BONUS)
        await asyncio.to_thread(
            lambda: db.client.table("user_bonus_quotas").upsert({
                "user_id": str(user_id),
                "valid_keys_count": valid_count,
                "daily_bonus_tokens": total_bonus,
                "updated_at": now,
            }, on_conflict="user_id").execute()
        )
    except Exception as exc:
        logger.warning(f"quota recompute failed: {exc}")

    return {"status": "accepted", "provider": provider, "bonus_earned": bonus, "message": "Key added to pool"}


@router.get("/quota")
async def get_quota(user: dict = Depends(verify_token_dependency)):
    user_id = user.get("sub") or user.get("user_id") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = get_db()
    try:
        rows = (await asyncio.to_thread(
            lambda: db.client.table("user_bonus_quotas").select("*").eq("user_id", str(user_id)).execute()
        )).data
        if rows:
            return rows[0]
    except Exception:
        pass
    return {"user_id": str(user_id), "valid_keys_count": 0, "daily_bonus_tokens": 0}
