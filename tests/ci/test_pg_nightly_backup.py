"""Offline checks of the nightly encrypted DB backup (admin Step 5)."""

import json
import subprocess
from pathlib import Path

import pytest

from scripts.backup import pg_nightly_backup as bk

POOLER_TX = "postgresql://postgres.ref:s3cr3t@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"


def test_pooler_transaction_mode_is_rewritten_to_session_mode():
    url = bk.session_mode_url(POOLER_TX)
    assert ":5432/postgres" in url
    assert ":6543" not in url
    assert "sslmode=require" in url
    assert "postgres.ref:s3cr3t@" in url  # credentials preserved for pg_dump


def test_non_pooler_and_existing_sslmode_are_untouched():
    url = "postgresql://u:p@db.example.com:6543/app?sslmode=verify-full"
    assert bk.session_mode_url(url) == url


def test_resolve_prefers_pooler_and_reports_only_the_env_name():
    url, source = bk.resolve_db_url({
        "SUPABASE_DATABASE_URL": "postgresql://u:p@direct:5432/postgres",
        "SUPABASE_DATABASE_URL_POOLER": f'"{POOLER_TX}"',
    })
    assert source == "SUPABASE_DATABASE_URL_POOLER"
    assert url.startswith("postgresql://postgres.ref:s3cr3t@")


def test_resolve_without_any_url_fails_closed():
    with pytest.raises(bk.BackupError, match="No database URL"):
        bk.resolve_db_url({})


def test_redact_never_contains_credentials():
    shown = bk.redact(bk.session_mode_url(POOLER_TX))
    assert "s3cr3t" not in shown and "postgres.ref" not in shown
    assert shown == "aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"


def test_pg_dump_command_scopes_schemas_and_skips_log_data(tmp_path):
    cmd = bk.pg_dump_cmd("postgresql://x", tmp_path / "o.dump")
    assert cmd[0] == "pg_dump" and "--format=custom" in cmd
    assert "--schema=public" in cmd and "--schema=auth" in cmd
    assert "--exclude-table-data=public.evolution_logs" in cmd
    assert "--no-owner" in cmd


def test_encryption_key_is_passed_by_env_never_argv(tmp_path):
    cmd = bk.encrypt_cmd(tmp_path / "a", tmp_path / "b")
    assert "env:BACKUP_ENCRYPTION_KEY" in cmd
    assert "-pbkdf2" in cmd and "-aes-256-cbc" in cmd


def test_missing_encryption_key_refuses_before_dumping(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(bk.BackupError, match="BACKUP_ENCRYPTION_KEY"):
        bk.run(tmp_path, {"SUPABASE_DATABASE_URL": "postgresql://u:p@h:5432/d"})
    assert called == []


class _Done:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _fake_tools(tables_listing: str, dump_rc: int = 0):
    def fake_run(cmd, **kwargs):
        tool = cmd[0]
        if tool == "pg_dump" and "--version" in cmd:
            return _Done("pg_dump (PostgreSQL) 17.2")
        if tool == "pg_dump":
            if dump_rc:
                return _Done(returncode=dump_rc, stderr="connection refused")
            out = next(a.split("=", 1)[1] for a in cmd if a.startswith("--file="))
            Path(out).write_bytes(b"PGDMP fake")
            return _Done()
        if tool == "pg_restore":
            return _Done(tables_listing)
        if tool == "openssl":
            Path(cmd[cmd.index("-out") + 1]).write_bytes(b"Salted__encrypted")
            return _Done()
        raise AssertionError(cmd)
    return fake_run


ENV = {"BACKUP_ENCRYPTION_KEY": "k" * 40, "SUPABASE_DATABASE_URL_POOLER": POOLER_TX}


def test_run_writes_encrypted_dump_and_secret_free_manifest(tmp_path, monkeypatch):
    listing = "1; 0 0 TABLE DATA public users\n2; 0 0 TABLE DATA public chats\n3; 0 0 TABLE public x\n"
    monkeypatch.setattr(subprocess, "run", _fake_tools(listing))
    manifest = bk.run(tmp_path, ENV)
    assert (tmp_path / bk.DUMP_NAME).read_bytes().startswith(b"Salted__")
    assert not list(tmp_path.glob("*.dump"))  # plaintext never lands in the artifact dir
    on_disk = json.loads((tmp_path / bk.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert manifest["table_data_entries"] == 2
    assert manifest["db_url_source"] == "SUPABASE_DATABASE_URL_POOLER"
    raw = json.dumps(manifest)
    assert "s3cr3t" not in raw and "k" * 40 not in raw and "pooler.supabase.com" not in raw


def test_empty_dump_is_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_tools("3; 0 0 TABLE public x\n"))
    with pytest.raises(bk.BackupError, match="no table data"):
        bk.run(tmp_path, ENV)
    assert not (tmp_path / bk.DUMP_NAME).exists()


def test_pg_dump_failure_is_reported_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_tools("", dump_rc=1))
    with pytest.raises(bk.BackupError) as exc:
        bk.run(tmp_path, ENV)
    assert "exit 1" in str(exc.value) and "s3cr3t" not in str(exc.value)
