"""Ramp coverage for tools/security_tools/multi_account_rotator.py (round: 66% -> 100%).

The merged suite (test_multi_account_rotator.py, #295) deliberately scoped OUT the
browser orchestration. This ramp covers the remaining arms WITHOUT a live browser
and without touching owner code:

- _wait_for_verification: Firestore-first path (fake google.cloud.firestore module
  injected into sys.modules — wins with or without the real package), the SQLite
  fallback (fake os.path.exists / sqlite3.connect), loop timeout fall-through,
  and both CancelledError re-raise guards.
- perform_autonomous_signup: full Playwright flow via a fake playwright.async_api
  (same lazy-import seam), instance-patched _wait_for_verification /
  _extract_api_key_from_dashboard, every warning ("continuing") arm, the
  PENDING_KEY_EXTRACTION status path, and the error/cancel exits.
- _load_providers_from_config: every status-string conversion arm for providers
  and accounts, the no-status/no-accounts arcs, live (non-dict) account pass-through,
  unparseable-timestamp coercion to None, and malformed-account skip.
- Defensive guards: load_config CancelledError re-raise, add_account's
  "not found even after creation attempt", extraction None-element/cancel/outer-guard
  arms, task-key coercion for objects, string-keyed preferences with missing and
  inactive providers, requirements-rejection loop arc, execute/_call_api/failover
  CancelledError re-raises, and main() with test keys present.

Wire-first note: zero changes to owner code; quirks are documented where found.
"""

import asyncio
import json
import sqlite3
import sys
import types
from datetime import datetime
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import backend.tools.security_tools.multi_account_rotator as rotator_mod
from backend.tools.security_tools.multi_account_rotator import (
    Account,
    MultiAccountRotator,
    Provider,
    ProviderStatus,
    TaskType,
)

# ============================================================
# helpers
# ============================================================


def make_account(account_id="acc-1", provider="groq", **overrides):
    # NOTE: owner default for Account.status is INACTIVE ("starts as inactive") —
    # selection-capable fixtures must opt into ACTIVE explicitly, matching #295 style.
    base = dict(
        id=account_id,
        provider=provider,
        email=f"{account_id}@example.com",
        api_key="sk-test",
        status=ProviderStatus.ACTIVE,
    )
    base.update(overrides)
    return Account(**base)


def make_provider(name="groq", accounts=None, status=ProviderStatus.ACTIVE, **overrides):
    base = dict(
        name=name,
        base_url=f"https://api.{name}.com",
        models=["default-model"],
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
        accounts=accounts or [],
        status=status,
        cost_per_token=0.0001,
    )
    base.update(overrides)
    return Provider(**base)


def make_rotator(tmp_path):
    return MultiAccountRotator(config_file=str(tmp_path / "rotation_config.json"))


def full_account_dict(account_id="a1", **overrides):
    data = {
        "id": account_id,
        "provider": "groq",
        "email": f"{account_id}@example.com",
        "api_key": "sk-1",
        "total_requests": 0,
        "failed_requests": 0,
        "rate_limit_hits": 0,
        "quota_used": 0,
        "quota_limit": 100,
    }
    data.update(overrides)
    return data


def full_provider_dict(name="groq", **overrides):
    data = {
        "name": name,
        "base_url": f"https://api.{name}.com",
        "models": ["default-model"],
        "rate_limit_rpm": 60,
        "rate_limit_tpm": 100000,
        "accounts": [],
    }
    data.update(overrides)
    return data


# ============================================================
# fake infrastructure: Firestore
# ============================================================


class FakeFirestoreDoc:
    def __init__(self, data, doc_id, updates):
        self._data = dict(data)
        self.id = doc_id
        self._updates = updates
        self.reference = SimpleNamespace(update=lambda patch: self._updates.append(dict(patch)))

    def to_dict(self):
        return dict(self._data)


class FakeFirestoreQuery:
    def __init__(self, docs):
        self._docs = docs

    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def stream(self):
        return list(self._docs)


class FakeFirestoreCollection:
    def __init__(self, docs):
        self._docs = docs

    def where(self, *args, **kwargs):
        return FakeFirestoreQuery(self._docs)


class FakeFirestoreDB:
    def __init__(self, docs, updates):
        self._docs = docs
        self._updates = updates

    def collection(self, name):
        assert name == "verification_queue"
        return FakeFirestoreCollection(self._docs)


def install_firestore(monkeypatch, docs=None, updates=None, client_error=None):
    """Inject a fake google.cloud.firestore package into sys.modules."""
    updates = updates if updates is not None else []
    docs = docs if docs is not None else []

    def client_factory():
        if client_error is not None:
            raise client_error
        return FakeFirestoreDB(docs, updates)

    fake_fs = types.ModuleType("google.cloud.firestore")
    fake_fs.Client = client_factory
    fake_fs.Query = SimpleNamespace(DESCENDING="desc")
    fake_cloud = types.ModuleType("google.cloud")
    fake_cloud.firestore = fake_fs
    fake_google = types.ModuleType("google")
    fake_google.cloud = fake_cloud
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.cloud", fake_cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", fake_fs)
    return updates


# ============================================================
# fake infrastructure: SQLite fallback
# ============================================================


class FakeSqliteCursor:
    def __init__(self, row):
        self._row = row
        self._last_sql = ""

    def execute(self, sql, *args):
        self._last_sql = sql

    def fetchone(self):
        if "sqlite_master" in self._last_sql:
            return ("verification_queue",)
        return self._row


class FakeSqliteConn:
    def __init__(self, row=None, connect_error=None):
        self._row = row
        self._connect_error = connect_error
        self.committed = False
        self.closed = False

    def cursor(self):
        if self._connect_error is not None:
            raise self._connect_error
        return FakeSqliteCursor(self._row)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def install_sqlite(monkeypatch, row=None, connect_error=None):
    conn = FakeSqliteConn(row=row, connect_error=connect_error)
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: conn)
    return conn


def install_db_path_exists(monkeypatch, exists_value):
    """Force os.path.exists True/False only for the rotator's verification DB path."""
    import os as os_module

    real_exists = os_module.path.exists

    def fake_exists(path):
        if isinstance(path, str) and path.endswith("supreme_memory.db"):
            return exists_value
        return real_exists(path)

    monkeypatch.setattr(os_module.path, "exists", fake_exists)


def install_fast_sleep(monkeypatch):
    """Replace asyncio.sleep with an immediate coroutine (loop tests must not stall)."""

    async def _instant(*args, **kwargs):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


# ============================================================
# fake infrastructure: Playwright
# ============================================================


class FakePlaywrightPage:
    def __init__(self, goto_error=None, fill_error=None, confirm_error=None):
        self.goto_calls = []
        self.fill_calls = []
        self.click_calls = []
        self.selector_calls = []
        self._goto_error = goto_error
        self._fill_error = fill_error
        self._confirm_error = confirm_error

    async def goto(self, url):
        self.goto_calls.append(url)
        if self._goto_error is not None:
            raise self._goto_error

    async def fill(self, selector, value):
        self.fill_calls.append((selector, value))
        if self._fill_error is not None:
            raise self._fill_error

    async def click(self, selector):
        self.click_calls.append(selector)

    async def wait_for_selector(self, selector, timeout=None):
        self.selector_calls.append(selector)
        if self._confirm_error is not None and "Account Created" in selector:
            raise self._confirm_error
        return SimpleNamespace(text="Account Created Successfully")


def install_playwright(monkeypatch, page):
    """Inject a fake playwright.async_api; browser close is observable."""
    closed = {"count": 0}

    class FakeBrowser:
        async def new_page(self):
            return page

        async def close(self):
            closed["count"] += 1

    class FakeChromium:
        async def launch(self, headless=True):
            assert headless is True
            return FakeBrowser()

    fake_api = types.ModuleType("playwright.async_api")

    class _AsyncPlaywrightCM:
        # dunders are looked up on the TYPE — a SimpleNamespace instance would
        # fail with 'does not support the asynchronous context manager protocol'
        async def __aenter__(self):
            return SimpleNamespace(chromium=FakeChromium())

        async def __aexit__(self, *exc):
            return False

    def async_playwright():
        return _AsyncPlaywrightCM()

    fake_api.async_playwright = async_playwright
    fake_root = types.ModuleType("playwright")
    fake_root.async_api = fake_api
    monkeypatch.setitem(sys.modules, "playwright", fake_root)
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_api)
    return closed


# ============================================================
# _wait_for_verification
# ============================================================


@pytest.mark.asyncio
async def test_verification_found_via_firestore(tmp_path, monkeypatch):
    updates = []
    install_firestore(monkeypatch, docs=[FakeFirestoreDoc({"code": "123456"}, "doc-1", updates)])
    rotator = make_rotator(tmp_path)
    data = await rotator._wait_for_verification("acct@example.com", timeout=1)
    assert data["code"] == "123456"
    assert data["id"] == "doc-1"
    assert updates == [{"processed": True}]


@pytest.mark.asyncio
async def test_verification_firestore_fails_falls_back_to_sqlite(tmp_path, monkeypatch):
    install_firestore(monkeypatch, client_error=RuntimeError("no creds"))
    install_db_path_exists(monkeypatch, True)
    conn = install_sqlite(monkeypatch, row={"id": 7, "email_target": "a@b.com", "code": "c9"})
    install_fast_sleep(monkeypatch)
    rotator = make_rotator(tmp_path)
    data = await rotator._wait_for_verification("a@b.com", timeout=0.5)
    assert data["id"] == 7
    assert data["code"] == "c9"
    assert conn.committed is True
    assert conn.closed is True


@pytest.mark.asyncio
async def test_verification_sqlite_loop_without_db_file(tmp_path, monkeypatch):
    """No Firestore, no DB file: loop spins until timeout, returns None."""
    install_firestore(monkeypatch, client_error=RuntimeError("no creds"))
    install_db_path_exists(monkeypatch, False)
    install_fast_sleep(monkeypatch)
    rotator = make_rotator(tmp_path)
    assert await rotator._wait_for_verification("a@b.com", timeout=0.2) is None


@pytest.mark.asyncio
async def test_verification_sqlite_table_missing_keeps_polling(tmp_path, monkeypatch):
    """DB file exists but verification_queue table absent: fetchone None, keep polling."""
    install_firestore(monkeypatch, client_error=RuntimeError("no creds"))
    install_db_path_exists(monkeypatch, True)

    conn = FakeSqliteConn(row=None)

    class NoTableCursor(FakeSqliteCursor):
        def fetchone(self):
            # sqlite_master query finds nothing -> table missing
            return None

    conn.cursor = lambda: NoTableCursor(None)
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: conn)
    install_fast_sleep(monkeypatch)
    rotator = make_rotator(tmp_path)
    assert await rotator._wait_for_verification("a@b.com", timeout=0.2) is None
    assert conn.closed is True


@pytest.mark.asyncio
async def test_verification_zero_timeout_skips_both_loops(tmp_path, monkeypatch):
    install_firestore(monkeypatch, client_error=RuntimeError("no creds"))
    rotator = make_rotator(tmp_path)
    assert await rotator._wait_for_verification("a@b.com", timeout=0) is None


@pytest.mark.asyncio
async def test_verification_cancelled_during_firestore_client(tmp_path, monkeypatch):
    install_firestore(monkeypatch, client_error=asyncio.CancelledError())
    rotator = make_rotator(tmp_path)
    with pytest.raises(asyncio.CancelledError):
        await rotator._wait_for_verification("a@b.com", timeout=1)


@pytest.mark.asyncio
async def test_verification_firestore_ok_but_queue_empty_polls_until_timeout(tmp_path, monkeypatch):
    """Firestore reachable but no matching doc: loop iterates (sleep each pass)
    until the timeout expires, then falls through to the (absent) SQLite store."""
    install_firestore(monkeypatch, docs=[])  # Client() succeeds, stream() is empty
    install_db_path_exists(monkeypatch, False)
    install_fast_sleep(monkeypatch)
    rotator = make_rotator(tmp_path)
    assert await rotator._wait_for_verification("nobody@example.com", timeout=0.2) is None


@pytest.mark.asyncio
async def test_verification_sqlite_row_not_yet_present_keeps_polling(tmp_path, monkeypatch):
    """Table exists but the matching row hasn't arrived: close + re-poll to timeout."""
    install_firestore(monkeypatch, client_error=RuntimeError("no creds"))
    install_db_path_exists(monkeypatch, True)
    conn = FakeSqliteConn(row=None)  # sqlite_master finds table, SELECT finds no row
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: conn)
    install_fast_sleep(monkeypatch)
    rotator = make_rotator(tmp_path)
    assert await rotator._wait_for_verification("a@b.com", timeout=0.2) is None
    assert conn.closed is True


@pytest.mark.asyncio
async def test_verification_sqlite_connect_crash_is_logged_not_fatal(tmp_path, monkeypatch):
    install_firestore(monkeypatch, client_error=RuntimeError("no creds"))
    install_db_path_exists(monkeypatch, True)

    def broken_connect(*args, **kwargs):
        raise RuntimeError("disk I/O error")

    monkeypatch.setattr(sqlite3, "connect", broken_connect)
    rotator = make_rotator(tmp_path)
    assert await rotator._wait_for_verification("a@b.com", timeout=1) is None


@pytest.mark.asyncio
async def test_verification_cancelled_inside_sqlite_fallback(tmp_path, monkeypatch):
    install_firestore(monkeypatch, client_error=RuntimeError("no creds"))
    install_db_path_exists(monkeypatch, True)
    install_sqlite(monkeypatch, connect_error=asyncio.CancelledError())
    rotator = make_rotator(tmp_path)
    with pytest.raises(asyncio.CancelledError):
        await rotator._wait_for_verification("a@b.com", timeout=1)


# ============================================================
# perform_autonomous_signup
# ============================================================


@pytest.mark.asyncio
async def test_signup_rejects_non_whitelisted_provider(tmp_path):
    rotator = make_rotator(tmp_path)
    assert await rotator.perform_autonomous_signup("sketchy_provider") is False
    assert rotator.providers == {}


@pytest.mark.asyncio
async def test_signup_success_extracts_key_and_activates_account(tmp_path, monkeypatch):
    page = FakePlaywrightPage()
    closed = install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)  # verification-queue writes stay out of the real data dir
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)
    rotator._wait_for_verification = AsyncMock(return_value={"code": "654321"})
    rotator._extract_api_key_from_dashboard = AsyncMock(return_value="sk-extracted-123")

    assert await rotator.perform_autonomous_signup("groq") is True

    account = rotator.providers["groq"].accounts[0]
    assert account.status is ProviderStatus.ACTIVE
    assert account.api_key == "sk-extracted-123"
    assert account.password.startswith("Pass-")
    assert account.email.startswith("supremeai+")
    # OTP was submitted through the page
    assert ('input[id="otp-code"]', "654321") in page.fill_calls
    assert closed["count"] == 1
    with open(rotator.config_file) as f:
        saved = json.load(f)
    assert saved["providers"][0]["accounts"][0]["api_key"] == "sk-extracted-123"


@pytest.mark.asyncio
async def test_signup_verification_link_navigates_and_pends_key(tmp_path, monkeypatch):
    page = FakePlaywrightPage()
    install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)
    rotator._wait_for_verification = AsyncMock(
        return_value={"link": "https://verify.example.com/tok"}
    )
    rotator._extract_api_key_from_dashboard = AsyncMock(return_value=None)

    assert await rotator.perform_autonomous_signup("deepseek") is True

    account = rotator.providers["deepseek"].accounts[0]
    assert account.status is ProviderStatus.PENDING_KEY_EXTRACTION
    assert account.api_key is None
    assert "https://verify.example.com/tok" in page.goto_calls


@pytest.mark.asyncio
async def test_signup_form_and_confirmation_errors_continue(tmp_path, monkeypatch):
    """Every 'warning + continuing' arm must not abort the signup flow."""
    page = FakePlaywrightPage(
        fill_error=RuntimeError("selector mismatch"),
        confirm_error=TimeoutError("banner never appeared"),
    )
    install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)
    rotator._wait_for_verification = AsyncMock(return_value={"code": "111111"})
    rotator._extract_api_key_from_dashboard = AsyncMock(return_value="gsk_recovered_123")

    assert await rotator.perform_autonomous_signup("groq") is True
    assert rotator.providers["groq"].accounts[0].status is ProviderStatus.ACTIVE


@pytest.mark.asyncio
async def test_signup_no_verification_data_returns_false(tmp_path, monkeypatch):
    page = FakePlaywrightPage()
    closed = install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)
    rotator._wait_for_verification = AsyncMock(return_value=None)

    assert await rotator.perform_autonomous_signup("groq") is False
    assert rotator.providers == {}
    assert closed["count"] == 1  # finally-block browser close still runs


@pytest.mark.asyncio
async def test_signup_verification_without_code_or_link_skips_otp(tmp_path, monkeypatch):
    """Verification payload carrying neither code nor link: OTP/link arms skipped,
    flow continues straight to the account-created confirmation."""
    page = FakePlaywrightPage()
    install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)
    rotator._wait_for_verification = AsyncMock(return_value={"sender": "noreply"})
    rotator._extract_api_key_from_dashboard = AsyncMock(return_value="sk-key-987654")

    assert await rotator.perform_autonomous_signup("groq") is True
    assert rotator.providers["groq"].accounts[0].status is ProviderStatus.ACTIVE
    assert page.goto_calls == ["https://example.com/signup"]  # never navigated elsewhere


@pytest.mark.asyncio
async def test_signup_page_crash_returns_false_and_closes_browser(tmp_path, monkeypatch):
    page = FakePlaywrightPage(goto_error=RuntimeError("net::ERR_CONNECTION_REFUSED"))
    closed = install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)

    assert await rotator.perform_autonomous_signup("groq") is False
    assert closed["count"] == 1
    assert rotator.providers == {}


@pytest.mark.asyncio
async def test_signup_cancelled_propagates_and_closes_browser(tmp_path, monkeypatch):
    page = FakePlaywrightPage(goto_error=asyncio.CancelledError())
    closed = install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)

    with pytest.raises(asyncio.CancelledError):
        await rotator.perform_autonomous_signup("groq")
    assert closed["count"] == 1


@pytest.mark.asyncio
async def test_signup_appends_to_existing_provider(tmp_path, monkeypatch):
    """Provider already registered: metadata creation is skipped, account is appended."""
    page = FakePlaywrightPage()
    install_playwright(monkeypatch, page)
    install_sqlite(monkeypatch)
    monkeypatch.setattr(rotator_mod.os, "makedirs", lambda *a, **k: None)
    rotator = make_rotator(tmp_path)
    rotator.providers["groq"] = make_provider("groq")
    rotator._wait_for_verification = AsyncMock(return_value={"code": "222222"})
    rotator._extract_api_key_from_dashboard = AsyncMock(return_value="sk-second-key")

    assert await rotator.perform_autonomous_signup("groq") is True
    assert len(rotator.providers["groq"].accounts) == 1
    assert rotator.providers["groq"].base_url == "https://api.groq.com"


# ============================================================
# _load_providers_from_config: every conversion arm
# ============================================================


def test_load_config_providers_covers_all_status_and_rebuild_arms(tmp_path):
    rotator = make_rotator(tmp_path)
    config = {
        "providers": [
            full_provider_dict(
                "groq",
                status="inactive",
                accounts=[
                    # invalid created_at -> coerced to None with a logged warning
                    full_account_dict(
                        "a1",
                        status="active",
                        created_at="definitely-not-a-date",
                        last_used="2026-01-02T03:04:05",
                        reset_time="also-bad",
                    ),
                    full_account_dict("a2", status="rate_limited"),
                    full_account_dict("a3", status="failed"),
                    full_account_dict("a4", status="maintenance"),
                    # no status key -> keeps dataclass default (INACTIVE)
                    full_account_dict("a5"),
                ],
            ),
            full_provider_dict(
                "deepseek",
                status="failed",
                accounts=[
                    full_account_dict("d1", provider="deepseek", status="pending_key_extraction"),
                    full_account_dict("d2", provider="deepseek", status="inactive"),
                    # missing required id/email -> Account() TypeError -> skipped
                    {"provider": "deepseek", "email": "x@y.com"},
                ],
            ),
            # non-dict container that still supports `in` passes through untouched
            # (see quirk test below: a live Account does NOT get this far)
            full_provider_dict(
                "cohere",
                status="maintenance",
                accounts=[
                    MappingProxyType({"id": "live-1", "provider": "cohere", "email": "l@c.com"})
                ],
            ),
            # unknown status strings: both elif chains fall through untouched
            full_provider_dict(
                "google_ai_studio",
                status="mystery_provider_state",
                accounts=[
                    full_account_dict(
                        "gai-1", provider="google_ai_studio", status="mystery_account_state"
                    )
                ],
            ),
            # no status AND no accounts key at all: both False arcs (447->470, 470->505)
            {
                "name": "openai",
                "base_url": "https://api.openai.com/v1",
                "models": ["gpt-4"],
                "rate_limit_rpm": 60,
                "rate_limit_tpm": 40000,
            },
            full_provider_dict("anthropic", status="pending_key_extraction"),
        ],
        "task_preferences": {"coding": ["groq"]},
    }

    rotator._load_providers_from_config(config)

    groq = rotator.providers["groq"]
    assert groq.status is ProviderStatus.INACTIVE
    a1, a2, a3, a4, a5 = groq.accounts
    assert a1.status is ProviderStatus.ACTIVE
    assert a1.created_at is None  # unparseable timestamp coerced, not crashed
    assert a1.last_used == datetime.fromisoformat("2026-01-02T03:04:05")
    assert a1.reset_time is None
    assert a2.status is ProviderStatus.RATE_LIMITED
    assert a3.status is ProviderStatus.FAILED
    assert a4.status is ProviderStatus.MAINTENANCE
    assert a5.status is ProviderStatus.INACTIVE

    deepseek = rotator.providers["deepseek"]
    assert deepseek.status is ProviderStatus.FAILED
    assert [acc.id for acc in deepseek.accounts] == ["d1", "d2"]  # malformed skipped
    assert deepseek.accounts[0].status is ProviderStatus.PENDING_KEY_EXTRACTION
    assert deepseek.accounts[1].status is ProviderStatus.INACTIVE

    cohere = rotator.providers["cohere"]
    assert cohere.status is ProviderStatus.MAINTENANCE
    # mapping-proxy entry kept as-is (non-dict arm 473-475)
    assert isinstance(cohere.accounts[0], MappingProxyType)

    openai = rotator.providers["openai"]
    assert openai.status is ProviderStatus.ACTIVE  # default when key absent
    assert openai.accounts == []

    gai = rotator.providers["google_ai_studio"]
    assert gai.status == "mystery_provider_state"  # unknown string survives untouched
    assert gai.accounts[0].status == "mystery_account_state"

    assert rotator.providers["anthropic"].status is ProviderStatus.PENDING_KEY_EXTRACTION
    assert rotator.task_preferences == {"coding": ["groq"]}


def test_load_config_cancellederror_reraises(tmp_path, monkeypatch):
    cfg = tmp_path / "r.json"
    cfg.write_text("{}")

    def cancelled_load(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(rotator_mod.json, "load", cancelled_load)
    with pytest.raises(asyncio.CancelledError):
        MultiAccountRotator(config_file=str(cfg))


def test_load_config_live_account_crashes_status_lookup(tmp_path):
    """OWNER QUIRK (documented, not patched — wire-first): the status-conversion
    loop at multi_account_rotator.py:449 runs '"status" in account_data' WITHOUT
    the isinstance(account_data, dict) guard that the rebuild block below it has.
    A live Account object (no __contains__/__iter__) therefore raises TypeError
    BEFORE the non-dict pass-through arm (473-475) can ever run for dataclasses.
    Only non-dict containers supporting `in` (mapping proxies, tuples) reach it."""
    rotator = make_rotator(tmp_path)
    config = {
        "providers": [full_provider_dict("groq", accounts=[make_account("live-1")])],
        "task_preferences": {},
    }
    with pytest.raises(TypeError, match="not iterable"):
        rotator._load_providers_from_config(config)


# ============================================================
# defensive guards
# ============================================================


def test_add_account_raises_when_creation_attempt_fails(tmp_path, monkeypatch):
    rotator = make_rotator(tmp_path)
    monkeypatch.setattr(rotator, "_create_provider_if_missing", lambda name: None)
    with pytest.raises(ValueError, match="not found even after creation attempt"):
        rotator.add_account("groq", "dev@example.com", "sk-key")


def test_task_key_accepts_any_object(tmp_path):
    rotator = make_rotator(tmp_path)

    class Mystery:
        pass

    # str-branch coercion (no .value, not a str) then falls through to no-capacity None
    assert rotator.get_best_provider_for_task(Mystery()) is None


def test_string_keyed_preferences_skip_missing_provider(tmp_path):
    rotator = make_rotator(tmp_path)
    rotator.task_preferences = {"coding": ["ghost", "groq"]}
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    result = rotator.get_best_provider_for_task(TaskType.CODING)
    assert result is not None and result[0].name == "groq"


def test_string_keyed_preferences_skip_inactive_provider(tmp_path):
    rotator = make_rotator(tmp_path)
    rotator.task_preferences = {"coding": ["deepseek", "groq"]}
    rotator.providers["deepseek"] = make_provider(
        "deepseek", accounts=[make_account("d1")], status=ProviderStatus.MAINTENANCE
    )
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    result = rotator.get_best_provider_for_task("coding")
    assert result is not None and result[0].name == "groq"


def test_requirements_failure_loops_to_next_provider(tmp_path):
    """765->744 arc: requirements reject provider 1, loop promotes provider 2."""
    rotator = make_rotator(tmp_path)
    rotator.task_preferences = {"coding": ["groq", "deepseek"]}
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    rotator.providers["deepseek"] = make_provider(
        "deepseek", accounts=[make_account("d1")], cost_per_token=0.0
    )
    result = rotator.get_best_provider_for_task(
        TaskType.CODING, requirements={"max_cost_per_token": 0.00005}
    )
    assert result is not None and result[0].name == "deepseek"


# ============================================================
# _extract_api_key_from_dashboard: remaining arms
# ============================================================


class NoneThenFoundPage:
    """First selector returns None (641->638 arc), second yields a key element."""

    def __init__(self, element):
        self._calls = 0
        self._element = element

    async def wait_for_selector(self, selector, timeout=None):
        self._calls += 1
        if self._calls == 1:
            return None
        return self._element


@pytest.mark.asyncio
async def test_extract_key_survives_none_element(tmp_path):
    rotator = make_rotator(tmp_path)
    element = SimpleNamespace(get_attribute=AsyncMock(return_value="sk-after-none-element"))
    key = await rotator._extract_api_key_from_dashboard(NoneThenFoundPage(element), "groq")
    assert key == "sk-after-none-element"


@pytest.mark.asyncio
async def test_extract_key_cancelled_propagates(tmp_path):
    class CancelledPage:
        async def wait_for_selector(self, selector, timeout=None):
            raise asyncio.CancelledError()

    rotator = make_rotator(tmp_path)
    with pytest.raises(asyncio.CancelledError):
        await rotator._extract_api_key_from_dashboard(CancelledPage(), "groq")


@pytest.mark.asyncio
async def test_extract_key_outer_guard_catches_handler_failure(tmp_path, monkeypatch):
    """Outer except arm: even a failing debug-log inside the selector loop
    must surface as a warning + None, not a crash."""

    class CrashingPage:
        async def wait_for_selector(self, selector, timeout=None):
            raise RuntimeError("selector exploded")

    monkeypatch.setattr(
        rotator_mod.logger,
        "debug",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("log sink down")),
    )
    rotator = make_rotator(tmp_path)
    assert await rotator._extract_api_key_from_dashboard(CrashingPage(), "groq") is None


# ============================================================
# execute / _call_api / failover: CancelledError arms
# ============================================================


@pytest.mark.asyncio
async def test_execute_task_cancelled_reraises(tmp_path):
    rotator = make_rotator(tmp_path)
    rotator.task_preferences = {"coding": ["groq"]}
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    rotator._call_api = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await rotator.execute_task(TaskType.CODING, "prompt")
    assert rotator.providers["groq"].accounts[0].total_requests == 0


@pytest.mark.asyncio
async def test_call_api_cancelled_reraises(tmp_path, monkeypatch):
    gateway = SimpleNamespace(acompletion=AsyncMock(side_effect=asyncio.CancelledError()))
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    rotator = make_rotator(tmp_path)
    with pytest.raises(asyncio.CancelledError):
        await rotator._call_api(make_provider("groq"), make_account("g1"), "prompt")


@pytest.mark.asyncio
async def test_failover_returns_none_when_no_capacity(tmp_path):
    rotator = make_rotator(tmp_path)
    assert await rotator._failover_execute(TaskType.CODING, "prompt") is None


@pytest.mark.asyncio
async def test_failover_breaks_when_selector_keeps_returning_same_provider(tmp_path):
    rotator = make_rotator(tmp_path)
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    rotator.task_preferences = {"coding": ["groq"]}
    rotator._call_api = AsyncMock(side_effect=RuntimeError("still down"))
    result = await rotator._failover_execute(TaskType.CODING, "prompt")
    assert result is None
    # one attempt total: pass 2 sees groq already in tried_providers -> break
    assert rotator.providers["groq"].accounts[0].failed_requests == 1


@pytest.mark.asyncio
async def test_failover_exhausts_three_distinct_providers(tmp_path):
    """887->915 arc: the for-loop runs out of attempts (no break). Only reachable
    with a selector yielding a NEW distinct provider every pass — the real
    selector deterministically re-returns the same best provider, so the loop
    would break on the tried-set check; instance-patched to the exhaustion shape."""
    rotator = make_rotator(tmp_path)
    sequence = [
        (make_provider("groq", accounts=[make_account("g1")]), make_account("g1")),
        (make_provider("deepseek", accounts=[make_account("d1")]), make_account("d1")),
        (make_provider("cohere", accounts=[make_account("c1")]), make_account("c1")),
    ]
    rotator.get_best_provider_for_task = lambda *a, **k: sequence.pop(0)
    rotator._call_api = AsyncMock(side_effect=RuntimeError("provider down"))

    assert await rotator._failover_execute(TaskType.CODING, "prompt") is None
    assert rotator._call_api.await_count == 3


@pytest.mark.asyncio
async def test_failover_cancelled_reraises(tmp_path):
    rotator = make_rotator(tmp_path)
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    rotator.task_preferences = {"coding": ["groq"]}
    rotator._call_api = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await rotator._failover_execute(TaskType.CODING, "prompt")


# ============================================================
# main() with test keys present
# ============================================================


@pytest.mark.asyncio
async def test_main_with_keys_accounts_stay_inactive_demo_cannot_execute(tmp_path, monkeypatch):
    """OWNER QUIRK (documented, not patched — wire-first): add_account() creates
    accounts with the dataclass default status INACTIVE ('starts as inactive'),
    and main() never activates them — so with test keys present the demo loop
    logs the failure branch for every task and the gateway is never called.
    The keys-present arms (977/979/981) and the no-result task arm still run."""
    monkeypatch.chdir(tmp_path)
    gateway = SimpleNamespace(
        acompletion=AsyncMock(return_value={"success": True, "text": "gateway answer"})
    )
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    monkeypatch.setattr(
        rotator_mod,
        "settings",
        SimpleNamespace(test_groq_key_1="k1", test_groq_key_2="k2", test_deepseek_key_1="k3"),
    )
    original = rotator_mod.rotator
    rotator_mod.rotator = None
    try:
        await rotator_mod.main()
        rotator = rotator_mod.rotator
        assert set(rotator.providers) == {"groq", "deepseek"}
        assert len(rotator.providers["groq"].accounts) == 2  # k1 + k2
        assert len(rotator.providers["deepseek"].accounts) == 1
        assert all(
            acc.status is ProviderStatus.INACTIVE
            for p in rotator.providers.values()
            for acc in p.accounts
        )
        # dead demo: zero gateway calls, zero recorded requests
        assert gateway.acompletion.await_count == 0
        assert rotator.providers["groq"].accounts[0].total_requests == 0
    finally:
        rotator_mod.rotator = original


@pytest.mark.asyncio
async def test_main_runs_tasks_when_accounts_activatable(tmp_path, monkeypatch):
    """Success arm of the demo loop (998-999): with accounts activatable the
    three tasks select groq's first account, call the gateway 3x, and log OK."""
    monkeypatch.chdir(tmp_path)
    gateway = SimpleNamespace(
        acompletion=AsyncMock(return_value={"success": True, "text": "gateway answer"})
    )
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    monkeypatch.setattr(
        rotator_mod,
        "settings",
        SimpleNamespace(test_groq_key_1="k1", test_groq_key_2="k2", test_deepseek_key_1="k3"),
    )

    real_account = rotator_mod.Account

    def activatable_account(**kwargs):
        acc = real_account(**kwargs)
        acc.status = ProviderStatus.ACTIVE
        return acc

    monkeypatch.setattr(rotator_mod, "Account", activatable_account)
    original = rotator_mod.rotator
    rotator_mod.rotator = None
    try:
        await rotator_mod.main()
        rotator = rotator_mod.rotator
        # three main() tasks all select groq's best account (dict-insertion order)
        assert rotator.providers["groq"].accounts[0].total_requests == 3
        assert gateway.acompletion.await_count == 3
    finally:
        rotator_mod.rotator = original
