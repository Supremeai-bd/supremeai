"""#3164 disaster-recovery durability tests — guard, off-container upload,
checksum verification, encryption, restore-from-durable.

# বাংলা মন্তব্য: প্রতিটি টেস্ট #3164 verification contract-এর বুলেট প্রমাণ করে:
# - runtime guard: ephemeral-disk destination-এ DR agent চালু হতে পারে না;
# - backup artifact অফ-কন্টেইনার যায় (mocked StorageClient, no network);
# - checksum verify (upload download-back + restore fail-closed);
# - optional Fernet at-rest encryption;
# - durable destination থেকে restore রিহার্সাল।
"""

from __future__ import annotations

import importlib.util
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

AGENT_PATH = Path(__file__).resolve().parents[2] / "agents" / "infrastructure" / "disaster_recovery_agent.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("dr_agent_under_test", AGENT_PATH)
    assert spec and spec.loader, "DR agent module spec load failed"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """বাংলা: বিচ্ছিন্ন DR agent instance — redis/settings বাইপাস ছাড়াই
    pure-layer methods টেস্ট করার জন্য env ক্লিন + staging dir tmp-তে।"""
    monkeypatch.delenv("DR_BACKUP_DESTINATION", raising=False)
    monkeypatch.delenv("DR_BACKUP_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("DR_ALLOW_EPHEMERAL_BACKUP", raising=False)
    monkeypatch.delenv("DR_BACKUP_RETENTION_DAYS", raising=False)
    mod = _load_module()
    monkeypatch.setattr(mod, "DR_STAGING_DIR", str(tmp_path / "staging"))
    # বাংলা: TokenDeductor/redis এড়াতে __new__ — শুধু durability layer টেস্ট
    inst = mod.DisasterRecoveryAgent.__new__(mod.DisasterRecoveryAgent)
    inst.name = "DR-test"
    inst.durable_destination = mod.DisasterRecoveryAgent._parse_durable_destination()
    return inst


class _FakeStorage:
    """বাংলা: in-memory StorageClient double — upload/download রাউন্ড-ট্রিপ
    সিমুলেট করে; কোনো network নেই।"""

    def __init__(self, provider: str = "supabase", corrupt: bool = False):
        self.provider = provider
        self.bucket_name = "test-bucket"
        self.objects: dict[str, bytes] = {}
        self.corrupt = corrupt

    def upload_file(self, local_path: str, remote_path: str) -> dict[str, Any]:
        with open(local_path, "rb") as f:
            data = f.read()
        if self.corrupt:
            data = data[:-4] + b"XXXX"  # বাংলা: ইচ্ছাকৃত দূষণ — checksum ধরার প্রমাণ
        self.objects[remote_path] = data
        return {"status": "success", "provider": self.provider, "path": remote_path}

    def download_file(self, remote_path: str, local_path: str) -> dict[str, Any]:
        if remote_path not in self.objects:
            return {"status": "error", "error": "not found"}
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(self.objects[remote_path])
        return {"status": "success", "provider": self.provider, "path": remote_path}


# ---------------------------------------------------------------------------
# Runtime guard — ephemeral destination ব্লক (#3164 core ask)
# ---------------------------------------------------------------------------
def test_guard_blocks_when_no_durable_destination(agent, monkeypatch):
    monkeypatch.delenv("DR_BACKUP_DESTINATION", raising=False)
    agent.durable_destination = agent._parse_durable_destination()
    assert agent.is_backup_destination_durable() is False


@pytest.mark.asyncio
async def test_create_backup_refuses_without_durable_destination(agent, monkeypatch, tmp_path):
    monkeypatch.delenv("DR_BACKUP_DESTINATION", raising=False)
    agent.durable_destination = None
    # বাংলা: components খালি দিলেও guard আগেই আটকাবে — archive তৈরিই হবে না
    result = await agent.create_backup(components=[])
    assert result.status == "failed"
    assert result.location == ""


@pytest.mark.asyncio
async def test_ephemeral_escape_hatch_allows_with_warning(agent, monkeypatch, tmp_path):
    monkeypatch.setenv("DR_ALLOW_EPHEMERAL_BACKUP", "true")
    monkeypatch.setattr(agent, "_create_backup_archive", _fake_archive(tmp_path))
    # বাংলা: location_override = escape-hatch পথের লিক্সি destination (CI-তে /backups নেই)
    result = await agent.create_backup(components=[], location_override=str(tmp_path / "local"))
    assert result.status == "success"
    assert result.location.startswith(str(tmp_path / "local"))


# ---------------------------------------------------------------------------
# Destination parsing
# ---------------------------------------------------------------------------
def test_parse_durable_destination_variants(agent, monkeypatch):
    monkeypatch.setenv("DR_BACKUP_DESTINATION", "supabase-storage://my-bucket/dr/backups")
    parsed = agent._parse_durable_destination()
    assert parsed == {"scheme": "supabase-storage", "bucket": "my-bucket", "prefix": "dr/backups"}

    monkeypatch.setenv("DR_BACKUP_DESTINATION", "s3://recovery-bucket/prefix/")
    parsed = agent._parse_durable_destination()
    assert parsed == {"scheme": "s3", "bucket": "recovery-bucket", "prefix": "prefix"}

    for bad in ("", "/backups/", "./local", "ftp://x/y", "supabase-storage:///"):
        monkeypatch.setenv("DR_BACKUP_DESTINATION", bad)
        assert agent._parse_durable_destination() is None, f"{bad!r} must not be durable"


# ---------------------------------------------------------------------------
# Verified durable upload — checksum + local staging cleanup
# ---------------------------------------------------------------------------
def _fake_archive(tmp_path: Path):
    """বাংলা: ছোট বৈধ zip তৈরির স্টাব — archive লেয়ার টেস্টের scope নয়।"""

    async def _make(archive_path: str, components: list[str]) -> int:
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("database/dump.sql", "SELECT 1;")
        return os.path.getsize(archive_path)

    return _make


@pytest.mark.asyncio
async def test_durable_upload_verifies_checksum_and_removes_local_copy(
    agent, monkeypatch, tmp_path
):
    monkeypatch.setenv("DR_BACKUP_DESTINATION", "supabase-storage://bk/dr")
    agent.durable_destination = agent._parse_durable_destination()

    fake = _FakeStorage()
    import types
    storage_module = types.ModuleType("database.storage_client")
    storage_module.StorageClient = lambda provider="supabase": fake
    monkeypatch.setitem(sys.modules, "database.storage_client", storage_module)
    monkeypatch.setattr(agent, "_create_backup_archive", _fake_archive(tmp_path))

    result = await agent.create_backup(components=[])
    assert result.status == "success"
    # বাংলা: location এখন durable URI — local staging path নয়
    assert result.location.startswith("supabase-storage://bk/dr/")
    assert result.location.endswith(".zip")
    # staged local zip মুছে গেছে
    assert not os.path.exists(os.path.join(str(tmp_path / "staging"), f"{result.backup_id}.zip"))
    # remote object সত্যিই আছে
    remote_key = result.location.split("bk/", 1)[1]
    assert remote_key in fake.objects


@pytest.mark.asyncio
async def test_durable_upload_fails_closed_on_corruption(agent, monkeypatch, tmp_path):
    monkeypatch.setenv("DR_BACKUP_DESTINATION", "supabase-storage://bk/dr")
    agent.durable_destination = agent._parse_durable_destination()

    import types
    storage_module = types.ModuleType("database.storage_client")
    storage_module.StorageClient = lambda provider="supabase": _FakeStorage(corrupt=True)
    monkeypatch.setitem(sys.modules, "database.storage_client", storage_module)
    monkeypatch.setattr(agent, "_create_backup_archive", _fake_archive(tmp_path))

    result = await agent.create_backup(components=[])
    # বাংলা: checksum mismatch → failed result — দূষিত artifact কখনো 'success' নয়
    assert result.status == "failed"


# ---------------------------------------------------------------------------
# Optional at-rest encryption (Fernet)
# ---------------------------------------------------------------------------
def test_encryption_key_from_env(agent, monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("DR_BACKUP_ENCRYPTION_KEY", key)
    assert agent._encryption_key() == key.encode()
    monkeypatch.delenv("DR_BACKUP_ENCRYPTION_KEY")
    assert agent._encryption_key() is None


@pytest.mark.asyncio
async def test_encrypted_upload_roundtrip(agent, monkeypatch, tmp_path):
    """বাংলা: এনক্রিপশন চালু থাকলে remote-এ ciphertext থাকবে; download+decrypt
    করলেই মূল zip ফেরত পাওয়া যায় — restore rehearsal চুক্তি।"""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    monkeypatch.setenv("DR_BACKUP_ENCRYPTION_KEY", key.decode())
    monkeypatch.setenv("DR_BACKUP_DESTINATION", "supabase-storage://bk/dr")
    agent.durable_destination = agent._parse_durable_destination()

    fake = _FakeStorage()
    import types
    storage_module = types.ModuleType("database.storage_client")
    storage_module.StorageClient = lambda provider="supabase": fake
    monkeypatch.setitem(sys.modules, "database.storage_client", storage_module)
    monkeypatch.setattr(agent, "_create_backup_archive", _fake_archive(tmp_path))

    result = await agent.create_backup(components=[])
    assert result.status == "success"
    remote_key = result.location.split("bk/", 1)[1]
    stored = fake.objects[remote_key]
    # বাংলা: stored bytes = Fernet token — খালি চোখে zip magic (PK) নেই
    assert not stored.startswith(b"PK")
    plain = Fernet(key).decrypt(stored)
    assert plain.startswith(b"PK")  # এখন বৈধ zip


# ---------------------------------------------------------------------------
# Restore rehearsal from durable destination — checksum fail-closed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_materialize_refuses_checksum_mismatch(agent, monkeypatch, tmp_path):
    monkeypatch.setenv("DR_BACKUP_DESTINATION", "supabase-storage://bk/dr")
    agent.durable_destination = agent._parse_durable_destination()

    import types
    fake = _FakeStorage()
    storage_module = types.ModuleType("database.storage_client")
    storage_module.StorageClient = lambda provider="supabase": fake
    monkeypatch.setitem(sys.modules, "database.storage_client", storage_module)
    fake.objects["dr/backup_x.zip"] = b"tampered-bytes"

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        await agent._materialize_durable_artifact(
            "supabase-storage://bk/dr/backup_x.zip",
            "0" * 64,  # বাংলা: ভুল expected hash
            "backup_x",
        )


@pytest.mark.asyncio
async def test_materialize_rejects_non_durable_location(agent, monkeypatch):
    monkeypatch.setenv("DR_BACKUP_DESTINATION", "supabase-storage://bk/dr")
    agent.durable_destination = agent._parse_durable_destination()
    with pytest.raises(ValueError, match="not a durable artifact"):
        await agent._materialize_durable_artifact("/backups/old.zip", None, "b1")


# ---------------------------------------------------------------------------
# Retention (staged local residue)
# ---------------------------------------------------------------------------
def test_local_retention_prunes_old_files(agent, tmp_path, monkeypatch):
    import time
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    old_file = staging / "old.zip"
    old_file.write_bytes(b"x")
    os.utime(old_file, (time.time() - 40 * 86400, time.time() - 40 * 86400))
    new_file = staging / "new.zip"
    new_file.write_bytes(b"x")

    removed = agent.apply_local_retention(retention_days=30)
    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()
