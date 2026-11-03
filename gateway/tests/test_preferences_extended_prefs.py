"""ERR-H01 regression tests — extended preference persistence.

Covers the /api/preferences contract used by ThemeProvider, themeStore,
I18nProvider and ProfilePage:
- extended surfaces (preferred_language, profile, security, notifications,
  verbosity, preferred_frameworks) are accepted and really persisted;
- they are stored inside the JSONB custom_shortcuts._extended key (the only
  free-form column) so no unknown-column 500 and no silent drops;
- GET hoists them back to top level for backward-compatible reads;
- offline mode (db.client None) still succeeds.
"""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import preferences as preferences_module


class _FakeResult:
    def __init__(self, data: Any):
        self.data = data


class _FakeTable:
    """Minimal chainable supabase-style builder for select/eq/upsert/execute."""

    def __init__(self, client: _FakeClient):
        self._client = client
        self._op = "select"

    def select(self, _cols: str) -> _FakeTable:
        self._op = "select"
        return self

    def eq(self, *_a: Any, **_k: Any) -> _FakeTable:
        return self

    def upsert(self, data: dict) -> _FakeTable:
        self._op = "upsert"
        self._client.upserts.append(dict(data))
        return self

    async def execute(self) -> _FakeResult:
        if self._op == "select":
            return _FakeResult(list(self._client.select_rows))
        return _FakeResult([dict(self._client.upserts[-1])])


class _FakeClient:
    def __init__(self) -> None:
        self.upserts: list[dict] = []
        self.select_rows: list[dict] = []

    def table(self, _name: str) -> _FakeTable:
        return _FakeTable(self)


@pytest.fixture()
def fake_db(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    client = _FakeClient()
    monkeypatch.setattr(preferences_module.db, "client", client)
    return client


@pytest.mark.asyncio
async def test_extended_prefs_persisted_in_custom_shortcuts(fake_db: _FakeClient) -> None:
    """I18nProvider / ProfilePage payloads persist without unknown-column errors."""
    payload = preferences_module.PreferenceUpdate(
        preferred_language="bn",
        profile={"name": "Saiful", "email": "s@example.com"},
        security={"jit_otp_enabled": True},
        notifications={"email": True, "push": False},
        verbosity="verbose",
    )
    resp = await preferences_module.upsert_preferences(payload, user_id="default")

    assert resp["status"] == "success"
    assert len(fake_db.upserts) == 1
    upserted = fake_db.upserts[0]
    # No non-physical column at the top level (pre-existing latent 500 removed).
    for forbidden in ("preferred_language", "profile", "security", "notifications", "verbosity"):
        assert forbidden not in upserted
    ext = upserted["custom_shortcuts"]["_extended"]
    assert ext["preferred_language"] == "bn"
    assert ext["profile"] == {"name": "Saiful", "email": "s@example.com"}
    assert ext["security"] == {"jit_otp_enabled": True}
    assert ext["notifications"] == {"email": True, "push": False}
    assert ext["verbosity"] == "verbose"


@pytest.mark.asyncio
async def test_get_hoists_extended_prefs(fake_db: _FakeClient) -> None:
    """GET returns _extended values as top-level keys (round trip works)."""
    fake_db.select_rows = [
        {
            "user_id": "default",
            "theme": "dark",
            "default_model": "gpt-4o",
            "max_tokens": 4096,
            "auto_save": True,
            "custom_shortcuts": {
                "ctrl+k": "palette",
                "_extended": {"preferred_language": "bn", "profile": {"name": "S"}},
            },
        }
    ]
    row = await preferences_module.get_preferences(user_id="default")
    assert row["preferred_language"] == "bn"
    assert row["profile"] == {"name": "S"}
    # unrelated shortcut keys preserved
    assert row["custom_shortcuts"]["ctrl+k"] == "palette"


@pytest.mark.asyncio
async def test_extended_prefs_merge_with_existing_shortcuts(fake_db: _FakeClient) -> None:
    """A second update merges into the stored _extended instead of replacing it."""
    fake_db.select_rows = [
        {"user_id": "default", "custom_shortcuts": {"_extended": {"preferred_language": "en"}}}
    ]
    await preferences_module.upsert_preferences(
        preferences_module.PreferenceUpdate(security={"jit_otp_enabled": False}),
        user_id="default",
    )
    ext = fake_db.upserts[0]["custom_shortcuts"]["_extended"]
    assert ext["preferred_language"] == "en"  # preserved
    assert ext["security"] == {"jit_otp_enabled": False}  # added


@pytest.mark.asyncio
async def test_offline_mode_still_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """db.client None (local dev) → success response, no crash, theme broadcast."""
    monkeypatch.setattr(preferences_module.db, "client", None)
    resp = await preferences_module.upsert_preferences(
        preferences_module.PreferenceUpdate(theme="dark", preferred_language="bn"),
        user_id="default",
    )
    assert resp["status"] == "success"
    assert resp["preferences"]["theme"] == "dark"
