"""SEC-HARDEN (Crown Jewel Module 18 / P-B) — Telegram admin identity truth.

Closes the identity defects of `docs/plans/crown_jewel_series/
MODULE_18_TELEGRAM_ORGAN_POWER_UP_2026-09-17.md` §P-B:

- a **hardcoded personal admin chat ID** lived in the bot source, and a second
  duplicate comparison made it **unrevocable** via env;
- the gate defaulted **fail-open** (no config ⇒ that hardcoded person stayed admin);
- `is_admin(chat_id)` used the *chat* id, so in group chats **any member** of a
  group whose id matched the config passed the admin gate.

Now: env/vault-only identity, fail-closed, and the **sender** (`from.id`) is
authoritative. Unit/source-level only — no heavy app fixtures, so these run in
the fast Critical/security tier (same convention as `test_hardening_controls.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import settings
from tools.social.telegram_bot.handler import TelegramBotCore

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
TELEGRAM_PKG = BACKEND_DIR / "tools" / "social" / "telegram_bot"

ADMIN = "111222333"
OTHER = "999888777"


def _gate() -> TelegramBotCore:
    """Gate instance built *without* __init__ (no network / no vault reads)."""
    return TelegramBotCore.__new__(TelegramBotCore)


@pytest.fixture()
def no_admin_config(monkeypatch):
    """Remove every configured admin identity source (settings + env)."""
    monkeypatch.setattr(settings, "admin_telegram_chat_id", "", raising=False)
    monkeypatch.delenv("ADMIN_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


@pytest.fixture()
def configured_admin(no_admin_config, monkeypatch):
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", ADMIN)
    return ADMIN


# ===========================================================================
# Source-level: the leaked identity + the fail-open pattern must be gone
# ===========================================================================
class TestNoHardcodedAdminIdentity:
    """Zero-hardcode doctrine: no admin identity may live in the source tree."""

    @pytest.mark.unit
    def test_leaked_personal_admin_id_removed_from_package(self):
        offenders = [
            path.name
            for path in TELEGRAM_PKG.glob("*.py")
            if "7804133572" in path.read_text(encoding="utf-8")
        ]
        assert not offenders, f"hardcoded admin identity still present in: {offenders}"

    @pytest.mark.unit
    def test_old_fail_open_default_pattern_is_gone(self):
        src = (TELEGRAM_PKG / "handler.py").read_text(encoding="utf-8")
        assert 'or "7804133572"' not in src
        assert 'str(chat_id) == "7804133572"' not in src

    @pytest.mark.unit
    def test_no_chat_id_only_admin_gate_remains(self):
        """Every admin gate call must stay sender-aware (no group-chat bypass)."""
        offenders: list[str] = []
        for path in TELEGRAM_PKG.glob("*.py"):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "is_admin(chat_id)" in line:
                    offenders.append(f"{path.name}:{lineno}")
        assert not offenders, f"sender-blind admin gate call site(s): {offenders}"


# ===========================================================================
# Behavioral: fail-closed gate + sender-authoritative identity
# ===========================================================================
class TestAdminGateFailClosed:
    @pytest.mark.unit
    def test_unconfigured_gate_denies_everyone(self, no_admin_config):
        gate = _gate()
        assert gate.is_admin(ADMIN) is False
        assert gate.is_admin(ADMIN, ADMIN) is False
        assert gate.is_admin(OTHER, OTHER) is False

    @pytest.mark.unit
    def test_configured_admin_is_allowed(self, configured_admin):
        gate = _gate()
        assert gate.is_admin(ADMIN) is True
        assert gate.is_admin(ADMIN, ADMIN) is True

    @pytest.mark.unit
    def test_non_admin_is_denied(self, configured_admin):
        gate = _gate()
        assert gate.is_admin(OTHER) is False
        assert gate.is_admin(OTHER, OTHER) is False

    @pytest.mark.unit
    def test_revoking_config_revokes_admin(self, configured_admin, monkeypatch):
        """Regression: the old hardcoded double-check made revocation impossible."""
        gate = _gate()
        assert gate.is_admin(ADMIN, ADMIN) is True
        monkeypatch.delenv("ADMIN_TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.setattr(settings, "admin_telegram_chat_id", "", raising=False)
        assert gate.is_admin(ADMIN, ADMIN) is False

    @pytest.mark.unit
    def test_group_member_cannot_pass_admin_gate(self, configured_admin):
        """chat_id == admin id (group id) but a *different* human wrote it."""
        gate = _gate()
        assert gate.is_admin(ADMIN, OTHER) is False

    @pytest.mark.unit
    def test_admin_still_works_dispatched_from_a_group(self, configured_admin):
        """Admin sends from a group: chat_id is the group, sender id is the admin."""
        gate = _gate()
        assert gate.is_admin("555000111", ADMIN) is True

    @pytest.mark.unit
    def test_empty_sender_is_denied(self, configured_admin):
        gate = _gate()
        assert gate.is_admin("", "") is False
        assert gate.is_admin("   ", "   ") is False

    @pytest.mark.unit
    def test_multiple_admins_comma_and_semicolon_separated(self, no_admin_config, monkeypatch):
        monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", f"{ADMIN}; {OTHER}")
        gate = _gate()
        assert gate.is_admin(ADMIN, ADMIN) is True
        assert gate.is_admin(OTHER, OTHER) is True
        assert gate.is_admin("404040404", "404040404") is False


class TestAdminIdentityIsNotDisclosed:
    @pytest.mark.unit
    def test_security_panel_never_prints_an_admin_id(self):
        src = (TELEGRAM_PKG / "admin_handlers.py").read_text(encoding="utf-8")
        assert "Admin Identity:</b> Telegram ID" not in src
        assert "admin_identity_state" in src
