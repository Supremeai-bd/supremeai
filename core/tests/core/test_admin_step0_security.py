"""Step 0 admin security regressions (impersonation, backups, config leak).

বাংলা মন্তব্য: impersonation টোকেন ১৫ মিনিটে শেষ, অ্যাডমিনকে impersonate নিষেধ,
অস্তিত্বহীন ইউজার 404; ব্যাকআপে `.env` কপি হয় না; restore/emergency-deploy সৎভাবে
501; /config-এ URL পাসওয়ার্ড মাস্ক।
"""

import asyncio
import json
import os

import jwt
import pytest
from fastapi import HTTPException

import api.routes.admin_dashboard as dash
from api.routes.admin_dashboard import endpoints_backups as backups
from api.routes.admin_dashboard import endpoints_config as cfg
from api.routes.admin_dashboard import endpoints_impersonate as imp
from api.routes.admin_dashboard._models import ImpersonateRequest
from core.config import settings


@pytest.fixture
def users_file(tmp_path, monkeypatch):
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            [
                {"username": "alice", "role": "user", "permissions": ["read"]},
                {"username": "root", "role": "admin", "permissions": ["all"]},
            ]
        )
    )
    monkeypatch.setattr(dash, "USERS_FILE", str(path))
    return path


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_impersonation_token_expires_in_15_minutes(users_file):
    res = _run(imp.impersonate_user("alice", current_admin={"uid": "owner"}))
    claims = jwt.decode(res["impersonation_token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["uid"] == "alice"
    assert claims["impersonation"] is True
    assert claims["impersonator"] == "owner"
    assert claims["exp"] - claims["iat"] == 15 * 60
    assert claims["jti"].startswith("imp_")
    assert res["expires_in"] == 15 * 60


def test_impersonation_rejects_unknown_user(users_file):
    with pytest.raises(HTTPException) as exc:
        _run(imp.impersonate_by_payload(ImpersonateRequest(user_id="ghost"), current_admin={}))
    assert exc.value.status_code == 404


def test_impersonation_refuses_admin_accounts(users_file):
    with pytest.raises(HTTPException) as exc:
        _run(imp.impersonate_user("root", current_admin={"uid": "owner"}))
    assert exc.value.status_code == 403


def test_expired_impersonation_token_is_rejected():
    claims = imp.build_impersonation_claims({"username": "alice"}, "owner", now=1_000)
    token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def test_backup_never_copies_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "users.json").write_text("[]")
    assert ".env" not in backups.BACKUP_SOURCE_FILES
    res = backups.trigger_backup()
    copied = os.listdir(res["backup_path"])
    assert "users.json" in copied
    assert ".env" not in copied


def test_restore_and_emergency_deploy_fail_honest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "backups" / "backup_x").mkdir(parents=True)
    with pytest.raises(HTTPException) as exc:
        backups.restore_backup("backup_x")
    assert exc.value.status_code == 501
    with pytest.raises(HTTPException) as exc:
        backups.restore_backup("../etc")
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc:
        backups.emergency_deploy()
    assert exc.value.status_code == 501


def test_config_masks_url_passwords(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:s3cret@db.example.com:5432/main")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    out = cfg.get_config()
    assert "s3cret" not in out["DATABASE_URL"]
    assert out["DATABASE_URL"] == "postgresql://app:***@db.example.com:5432/main"
    assert out["REDIS_URL"] == "redis://localhost:6379"
