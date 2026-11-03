"""Tests for tools/social/teldrive_storage.py — the TelDrive/Telegram zero-cost
encrypted storage engine.

Covers the client-side crypto layer end-to-end with REAL gzip + REAL Fernet
(round-trips, key-derivation fallback ladder, cross-key rejection), the upload
pipeline (chat-id resolution order, encryption naming/tags, caption metadata,
file-vs-bytes sources, bot boundary contract), and the DB backup archiver
(canonical table sweep, per-table/outer failure isolation, JSON serialization
of non-JSON row values, import-failure degradation).

Honesty boundaries: the ONLY faked components are the Telegram network
boundary (FakeTelDriveBot records every send_document call) and the database
session boundary (fake get_db_session / a sys.modules stub for the
import-failure path). Crypto, compression, hashing, file I/O and metadata
assembly are exercised for real.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import types
from datetime import datetime
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet, InvalidToken

import backend.tools.social.teldrive_storage as tds
from backend.tools.social.teldrive_storage import TelDriveCrypto, TelDriveStorage
from backend.tools.social.telegram_bot import TelegramBotHandler


def patch_get_db_session(monkeypatch, factory):
    """Patch the module object the function-under-test actually imports.

    teldrive_storage.create_and_upload_backup does `from database.session import
    get_db_session` at call time — a TOP-LEVEL `database.session` import, which
    under pytest resolves to a DIFFERENT module object than
    `backend.database.session` (verified: `a is b` -> False). Patch both so the
    helper is robust regardless of which alias a runner has warmed up.
    """
    import importlib

    for name in ("database.session", "backend.database.session"):
        try:
            mod = importlib.import_module(name)
        except Exception:  # pragma: no cover - alias unavailable in some runners
            continue
        monkeypatch.setattr(mod, "get_db_session", factory)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_KEY_SENTINEL = "supremeai-default-zero-cost-fernet-key-2026"


class FakeTelDriveBot:
    """Records send_document calls; scripted result. The network boundary."""

    _UNSET = object()

    def __init__(self, *, configured: bool = True, result=_UNSET) -> None:
        self._configured = configured
        self.result = {"ok": True, "result": {"message_id": 7}} if result is self._UNSET else result
        self.calls: list[dict] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def send_document(self, *, chat_id, document, filename, caption, parse_mode):
        self.calls.append(
            {
                "chat_id": chat_id,
                "document": document,
                "filename": filename,
                "caption": caption,
                "parse_mode": parse_mode,
            }
        )
        return self.result


class ExplodingKeySettings:
    """settings.encryption_key property that raises — exercises the except arm."""

    @property
    def encryption_key(self):
        raise RuntimeError("vault locked")

    admin_telegram_chat_id = ""


class StrKeySettings:
    """Plain-string encryption_key (no get_secret_value) — exercises str() arm."""

    encryption_key = "plain-string-key-for-teldrive-tests"
    admin_telegram_chat_id = ""


class EmptyKeySettings:
    encryption_key = ""
    admin_telegram_chat_id = ""


def swap_settings(monkeypatch, obj) -> None:
    monkeypatch.setattr(tds, "settings", obj)


def clear_chat_env(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("ADMIN_TELEGRAM_CHAT_ID", raising=False)


def derive_key(raw: str) -> bytes:
    import hashlib as _h

    return base64.urlsafe_b64encode(_h.sha256(raw.encode()).digest())


# ─────────────────────────────────────────────────────────────────────────────
# TelDriveCrypto — round-trips with real gzip + real Fernet
# ─────────────────────────────────────────────────────────────────────────────


class TestCryptoRoundTrips:
    def test_text_payload_round_trip(self, monkeypatch):
        swap_settings(monkeypatch, StrKeySettings())
        payload = "supremeai vault record 🚀".encode()
        token = TelDriveCrypto.encrypt_bytes(payload)
        assert TelDriveCrypto.decrypt_bytes(token) == payload

    def test_binary_payload_round_trip(self, monkeypatch):
        swap_settings(monkeypatch, StrKeySettings())
        payload = bytes(range(256)) * 17  # gzip-hostile high-entropy data
        token = TelDriveCrypto.encrypt_bytes(payload)
        assert TelDriveCrypto.decrypt_bytes(token) == payload

    def test_empty_payload_round_trip(self, monkeypatch):
        swap_settings(monkeypatch, StrKeySettings())
        assert TelDriveCrypto.decrypt_bytes(TelDriveCrypto.encrypt_bytes(b"")) == b""

    def test_compressible_payload_shrinks(self, monkeypatch):
        swap_settings(monkeypatch, StrKeySettings())
        payload = b"A" * 20000
        token = TelDriveCrypto.encrypt_bytes(payload)
        assert len(token) < len(payload) / 4

    def test_ciphertext_is_fernet_token_and_hides_payload(self, monkeypatch):
        swap_settings(monkeypatch, StrKeySettings())
        payload = b"top-secret-vault-bytes"
        token = TelDriveCrypto.encrypt_bytes(payload)
        assert token.startswith(b"gAAAAA")  # Fernet token version marker
        assert payload not in token

    def test_two_encrypts_of_same_payload_differ(self, monkeypatch):
        swap_settings(monkeypatch, StrKeySettings())
        # Fernet embeds a timestamp + random IV — ciphertext must be fresh.
        assert TelDriveCrypto.encrypt_bytes(b"x") != TelDriveCrypto.encrypt_bytes(b"x")

    def test_round_trip_via_default_settings_object(self):
        # REAL settings (no swap): the SettingsSecretsMixin.encryption_key
        # property feeds the cipher in the environment under test.
        payload = b"integration-with-real-settings"
        token = TelDriveCrypto.encrypt_bytes(payload)
        assert TelDriveCrypto.decrypt_bytes(token) == payload

    def test_decrypt_rejects_foreign_key(self, monkeypatch):
        class KeyA:
            encryption_key = "key-alpha"
            admin_telegram_chat_id = ""

        class KeyB:
            encryption_key = "key-beta"
            admin_telegram_chat_id = ""

        swap_settings(monkeypatch, KeyA())
        token = TelDriveCrypto.encrypt_bytes(b"payload-a")
        swap_settings(monkeypatch, KeyB())
        with pytest.raises(InvalidToken):
            TelDriveCrypto.decrypt_bytes(token)


# ─────────────────────────────────────────────────────────────────────────────
# TelDriveCrypto — key derivation fallback ladder
# ─────────────────────────────────────────────────────────────────────────────


class TestKeyDerivation:
    def test_secretstr_settings_key_is_used(self, monkeypatch):
        from pydantic import SecretStr

        swap_settings(monkeypatch, SimpleNamespace(encryption_key=SecretStr("unit-key-1")))
        fernet = TelDriveCrypto._get_fernet()
        expected = Fernet(derive_key("unit-key-1"))
        token = fernet.encrypt(b"m")
        assert expected.decrypt(token) == b"m"

    def test_plain_str_settings_key_is_used(self, monkeypatch):
        swap_settings(monkeypatch, StrKeySettings())
        fernet = TelDriveCrypto._get_fernet()
        expected = Fernet(derive_key("plain-string-key-for-teldrive-tests"))
        token = fernet.encrypt(b"m")
        assert expected.decrypt(token) == b"m"

    def test_raising_property_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", "env-fallback-key")
        swap_settings(monkeypatch, ExplodingKeySettings())
        fernet = TelDriveCrypto._get_fernet()
        expected = Fernet(derive_key("env-fallback-key"))
        token = fernet.encrypt(b"m")
        assert expected.decrypt(token) == b"m"

    def test_empty_key_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", "env-after-empty-key")
        swap_settings(monkeypatch, EmptyKeySettings())
        fernet = TelDriveCrypto._get_fernet()
        expected = Fernet(derive_key("env-after-empty-key"))
        token = fernet.encrypt(b"m")
        assert expected.decrypt(token) == b"m"

    def test_no_env_uses_builtin_default_key(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        swap_settings(monkeypatch, EmptyKeySettings())
        fernet = TelDriveCrypto._get_fernet()
        expected = Fernet(derive_key(DEFAULT_KEY_SENTINEL))
        token = fernet.encrypt(b"m")
        assert expected.decrypt(token) == b"m"

    def test_default_key_stable_across_calls(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        swap_settings(monkeypatch, EmptyKeySettings())
        token = TelDriveCrypto.encrypt_bytes(b"stable")
        assert TelDriveCrypto.decrypt_bytes(token) == b"stable"


# ─────────────────────────────────────────────────────────────────────────────
# TelDriveStorage — construction & configured delegation
# ─────────────────────────────────────────────────────────────────────────────


class TestConstruction:
    def test_explicit_handler_is_used(self):
        bot = FakeTelDriveBot()
        storage = TelDriveStorage(bot_handler=bot)
        assert storage.bot is bot
        assert storage.configured is True

    def test_default_constructor_builds_real_handler_without_token(self, monkeypatch):
        # Identity must be checked against the class object the module itself
        # uses: teldrive_storage imports `from tools.social.telegram_bot import
        # TelegramBotHandler` (top-level `tools` package) which under pytest is
        # a DISTINCT class object from `backend.tools.social.telegram_bot`.
        from tools.social.telegram_bot import TelegramBotHandler as TopLevelHandler

        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        storage = TelDriveStorage()
        assert isinstance(storage.bot, TopLevelHandler)
        assert type(storage.bot).__name__ == "TelegramBotHandler"
        assert storage.bot.bot_token == ""
        assert storage.configured is False

    def test_real_handler_rejects_mock_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_token")
        bot = TelegramBotHandler()
        assert bot.bot_token == "mock_token"
        assert bot.configured is False

    def test_real_handler_accepts_real_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "12345:real-unit-test-token")
        bot = TelegramBotHandler()
        assert bot.configured is True

    def test_configured_delegates_to_bot(self):
        assert TelDriveStorage(bot_handler=FakeTelDriveBot(configured=False)).configured is False


# ─────────────────────────────────────────────────────────────────────────────
# _default_chat_id — resolution order
# ─────────────────────────────────────────────────────────────────────────────


class TestDefaultChatId:
    def test_telegram_chat_id_env_wins(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "222")
        swap_settings(monkeypatch, SimpleNamespace(admin_telegram_chat_id="333"))
        assert TelDriveStorage(bot_handler=FakeTelDriveBot())._default_chat_id() == "111"

    def test_settings_chat_id_second(self, monkeypatch):
        clear_chat_env(monkeypatch)
        swap_settings(monkeypatch, SimpleNamespace(admin_telegram_chat_id="333"))
        assert TelDriveStorage(bot_handler=FakeTelDriveBot())._default_chat_id() == "333"

    def test_admin_env_chat_id_third(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "222")
        swap_settings(monkeypatch, SimpleNamespace(admin_telegram_chat_id=""))
        assert TelDriveStorage(bot_handler=FakeTelDriveBot())._default_chat_id() == "222"

    def test_no_source_yields_empty_string(self, monkeypatch):
        clear_chat_env(monkeypatch)
        swap_settings(monkeypatch, SimpleNamespace(admin_telegram_chat_id=""))
        assert TelDriveStorage(bot_handler=FakeTelDriveBot())._default_chat_id() == ""


# ─────────────────────────────────────────────────────────────────────────────
# upload_file — pipeline, naming, tags, metadata, boundary contract
# ─────────────────────────────────────────────────────────────────────────────


class TestUploadFile:
    async def test_no_chat_id_anywhere_returns_none_without_sending(self, monkeypatch):
        clear_chat_env(monkeypatch)
        swap_settings(monkeypatch, SimpleNamespace(admin_telegram_chat_id=""))
        bot = FakeTelDriveBot()
        result = await TelDriveStorage(bot_handler=bot).upload_file(b"data", "x.bin")
        assert result is None
        assert bot.calls == []

    async def test_bytes_upload_encrypted_with_enc_gz_suffix(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        raw = b"vault me"
        result = await TelDriveStorage(bot_handler=bot).upload_file(raw, "report.pdf")
        assert result == bot.result
        call = bot.calls[0]
        assert call["chat_id"] == "111"
        assert call["filename"] == "report.pdf.enc.gz"
        assert call["document"].startswith(b"gAAAAA")
        assert call["parse_mode"] == "HTML"
        assert TelDriveCrypto.decrypt_bytes(call["document"]) == raw

    async def test_enc_gz_suffix_not_doubled(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).upload_file(b"data", "already.enc.gz")
        assert bot.calls[0]["filename"] == "already.enc.gz"

    async def test_plaintext_upload_keeps_bytes_and_filename(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        raw = b"plain-and-proud"
        await TelDriveStorage(bot_handler=bot).upload_file(raw, "raw.bin", encrypt=False)
        call = bot.calls[0]
        assert call["document"] == raw
        assert call["filename"] == "raw.bin"
        assert "Plaintext Asset" in call["caption"]

    async def test_encrypted_caption_carries_encrypted_tag(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).upload_file(b"data", "a.bin")
        assert "Encrypted (AES-256)" in bot.calls[0]["caption"]

    async def test_default_category_hashtag(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).upload_file(b"data", "a.bin")
        assert "#GENERAL" in bot.calls[0]["caption"]

    async def test_category_uppercased_and_underscored(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).upload_file(b"data", "a.bin", category="db backup")
        assert "#DB_BACKUP" in bot.calls[0]["caption"]

    async def test_caption_contains_sha256_prefix_of_raw_bytes(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        raw = b"hash me please"
        await TelDriveStorage(bot_handler=bot).upload_file(raw, "a.bin")
        expected = hashlib.sha256(raw).hexdigest()[:16]
        assert f"<code>{expected}</code>" in bot.calls[0]["caption"]

    async def test_user_caption_appended(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).upload_file(b"data", "a.bin", caption="nightly drop")
        assert "💬 nightly drop" in bot.calls[0]["caption"]

    async def test_explicit_chat_id_beats_default(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).upload_file(b"data", "a.bin", chat_id="555")
        assert bot.calls[0]["chat_id"] == "555"

    async def test_file_path_source_is_read_and_encrypted(self, monkeypatch, tmp_path):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        src = tmp_path / "artifact.log"
        src.write_bytes(b"file-on-disk-content")
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).upload_file(str(src), "artifact.log")
        assert TelDriveCrypto.decrypt_bytes(bot.calls[0]["document"]) == b"file-on-disk-content"

    async def test_missing_file_path_returns_none_without_sending(self, monkeypatch, tmp_path):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        result = await TelDriveStorage(bot_handler=bot).upload_file(
            str(tmp_path / "ghost.bin"), "ghost.bin"
        )
        assert result is None
        assert bot.calls == []

    async def test_bot_failure_result_none_propagates(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot(result=None)
        assert await TelDriveStorage(bot_handler=bot).upload_file(b"data", "a.bin") is None

    async def test_caption_size_lines_reference_original_and_final_kb(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        bot = FakeTelDriveBot()
        raw = b"K" * 4096
        await TelDriveStorage(bot_handler=bot).upload_file(raw, "a.bin")
        caption = bot.calls[0]["caption"]
        assert "Size:" in caption
        assert f"(Original: {4096 / 1024:.1f} KB)" in caption


# ─────────────────────────────────────────────────────────────────────────────
# create_and_upload_backup — DB sweep, failure isolation, degradation
# ─────────────────────────────────────────────────────────────────────────────

CANONICAL_TABLES = [
    "ai_memory",
    "rules",
    "constitutional_rules",
    "conversations",
    "system_config",
    "agent_configs",
    "dynamic_skills",
]


class FakeSession:
    def __init__(self, rows_by_table=None, fail_tables=()):
        self.rows_by_table = rows_by_table or {}
        self.fail_tables = set(fail_tables)
        self.executed: list[str] = []

    async def execute(self, query):
        sql = str(query)
        self.executed.append(sql)
        for tbl in self.fail_tables:
            if f"FROM {tbl}" in sql:
                raise RuntimeError(f"table {tbl} exploded")
        for tbl, rows in self.rows_by_table.items():
            if f"FROM {tbl}" in sql:
                return [SimpleNamespace(_mapping=r) for r in rows]
        return []


class FakeGetDbSession:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


class ExplodingGetDbSession:
    async def __aenter__(self):
        raise RuntimeError("db down")

    async def __aexit__(self, *exc):
        return False


class TestCreateAndUploadBackup:
    async def test_happy_path_payload_round_trip(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        sess = FakeSession(
            rows_by_table={
                "rules": [{"id": 1, "name": "zero-cost"}, {"id": 2, "name": "wire-first"}],
                "conversations": [{"id": 10}],
            }
        )
        patch_get_db_session(monkeypatch, lambda: FakeGetDbSession(sess))
        bot = FakeTelDriveBot()
        assert await TelDriveStorage(bot_handler=bot).create_and_upload_backup() is True

        call = bot.calls[0]
        assert call["chat_id"] == "111"
        assert re.match(r"^supremeai_db_backup_\d{8}_\d{6}\.json\.enc\.gz$", call["filename"])
        payload = json.loads(TelDriveCrypto.decrypt_bytes(call["document"]))
        assert payload["version"] == "SupremeAI 2.0"
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$", payload["created_at"])
        assert payload["tables"]["rules"][1]["name"] == "wire-first"
        assert payload["tables"]["conversations"] == [{"id": 10}]
        # Every canonical table is recorded (empty sweep results included).
        assert set(payload["tables"]) == set(CANONICAL_TABLES)
        assert payload["metadata"]["table_count"] == 7
        assert payload["metadata"]["record_count"] == 3
        assert isinstance(payload["metadata"]["node"], str) and payload["metadata"]["node"]
        assert "#DB_BACKUP" in call["caption"]
        assert "3 records across 7 core tables" in call["caption"]

    async def test_canonical_table_sweep_with_limit_500(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        sess = FakeSession()
        patch_get_db_session(monkeypatch, lambda: FakeGetDbSession(sess))
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).create_and_upload_backup()
        assert set(sess.executed) == {f"SELECT * FROM {t} LIMIT 500" for t in CANONICAL_TABLES}

    async def test_failing_table_skipped_others_survive(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        sess = FakeSession(
            rows_by_table={"rules": [{"id": 1}], "conversations": [{"id": 2}]},
            fail_tables=("rules",),
        )
        patch_get_db_session(monkeypatch, lambda: FakeGetDbSession(sess))
        bot = FakeTelDriveBot()
        assert await TelDriveStorage(bot_handler=bot).create_and_upload_backup() is True
        payload = json.loads(TelDriveCrypto.decrypt_bytes(bot.calls[0]["document"]))
        assert "rules" not in payload["tables"]
        assert payload["tables"]["conversations"] == [{"id": 2}]
        assert payload["metadata"]["table_count"] == 6
        assert payload["metadata"]["record_count"] == 1

    async def test_outer_db_failure_still_uploads_empty_backup(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        patch_get_db_session(monkeypatch, lambda: ExplodingGetDbSession())
        bot = FakeTelDriveBot()
        assert await TelDriveStorage(bot_handler=bot).create_and_upload_backup() is True
        payload = json.loads(TelDriveCrypto.decrypt_bytes(bot.calls[0]["document"]))
        assert payload["tables"] == {}
        assert payload["metadata"]["table_count"] == 0
        assert payload["metadata"]["record_count"] == 0

    async def test_non_json_row_values_serialized_via_str(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        sess = FakeSession(
            rows_by_table={"ai_memory": [{"id": 1, "seen_at": datetime(2026, 9, 14, 10, 0, 0)}]}
        )
        patch_get_db_session(monkeypatch, lambda: FakeGetDbSession(sess))
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).create_and_upload_backup()
        payload = json.loads(TelDriveCrypto.decrypt_bytes(bot.calls[0]["document"]))
        assert payload["tables"]["ai_memory"][0]["seen_at"] == "2026-09-14 10:00:00"

    async def test_import_failure_degrades_to_empty_tables(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        stub = types.ModuleType("database.session")  # no get_db_session attr
        monkeypatch.setitem(sys.modules, "database.session", stub)
        bot = FakeTelDriveBot()
        assert await TelDriveStorage(bot_handler=bot).create_and_upload_backup() is True
        payload = json.loads(TelDriveCrypto.decrypt_bytes(bot.calls[0]["document"]))
        assert payload["tables"] == {}

    async def test_upload_failure_returns_false(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        patch_get_db_session(monkeypatch, lambda: FakeGetDbSession(FakeSession()))
        bot = FakeTelDriveBot(result=None)
        assert await TelDriveStorage(bot_handler=bot).create_and_upload_backup() is False

    async def test_chat_id_passthrough_to_upload(self, monkeypatch):
        clear_chat_env(monkeypatch)
        patch_get_db_session(monkeypatch, lambda: FakeGetDbSession(FakeSession()))
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).create_and_upload_backup(chat_id="777")
        assert bot.calls[0]["chat_id"] == "777"

    async def test_empty_table_kept_with_empty_list(self, monkeypatch):
        clear_chat_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
        sess = FakeSession(rows_by_table={"dynamic_skills": []})
        patch_get_db_session(monkeypatch, lambda: FakeGetDbSession(sess))
        bot = FakeTelDriveBot()
        await TelDriveStorage(bot_handler=bot).create_and_upload_backup()
        payload = json.loads(TelDriveCrypto.decrypt_bytes(bot.calls[0]["document"]))
        assert payload["tables"]["dynamic_skills"] == []
        assert payload["metadata"]["record_count"] == 0
        assert payload["metadata"]["table_count"] == 7
