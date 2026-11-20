"""The relay must publish session evidence the gateway can act on.

A stored cookie that has expired is this project's recurring silent failure: the
request returns "unavailable", the operator sees a healthy `/health` because
20 cookies are loaded, and the next request tries the same dead session. These
tests pin the two halves of the fix on the relay side:

* real request outcomes are recorded, and only an explicit auth status or
  challenge is allowed to claim EXPIRED / CHALLENGED — a guess stays UNKNOWN;
* `/health` publishes them under the **same engine ids** `/models` uses, because
  the gateway joins latency and session evidence on that key (publishing
  `gemini` while `/models` says `gemini-web` matches nothing, silently);
* nothing secret is published — only state, a short reason, an age and counts.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

# `conftest.py` already put browser/ on sys.path; importing the relay is then
# ordinary, and there is one copy of that bootstrap instead of one per file.
import server  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_session_state():
    server._session_state.clear()
    yield
    server._session_state.clear()


def test_health_publishes_session_evidence():
    payload = TestClient(server.app).get("/health").json()
    assert payload["status"] == "healthy"
    assert set(payload["sessions"]) == {"duck", "gemini-web"}
    gemini = payload["sessions"]["gemini-web"]
    assert gemini["state"] == "UNKNOWN"
    assert "cookie_present" in gemini and "cookie_count" in gemini
    assert gemini["age_s"] is None, "no request has run yet, so there is no age"


def test_published_ids_match_the_models_endpoint():
    """The join key. A rename on either side makes sessions invisible, not loud."""
    models = TestClient(server.app).get("/models").json()
    engine_ids = {row["id"] for row in models["data"]}
    sessions = TestClient(server.app).get("/health").json()["sessions"]
    assert set(sessions) == engine_ids


def test_a_successful_request_marks_the_session_ok():
    server.note_session("gemini", "OK")
    entry = server.session_snapshot()["gemini-web"]
    assert entry["state"] == "OK"
    assert entry["consecutive_failures"] == 0
    assert entry["age_s"] is not None


def test_failures_accumulate_and_reset_on_success():
    server.note_session("gemini", "EXPIRED", "HTTP 403")
    server.note_session("gemini", "EXPIRED", "HTTP 403")
    assert server.session_snapshot()["gemini-web"]["consecutive_failures"] == 2
    server.note_session("gemini", "OK")
    assert server.session_snapshot()["gemini-web"]["consecutive_failures"] == 0


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ("Gemini returned HTTP 403", "EXPIRED"),
        ("Gemini returned HTTP 401", "EXPIRED"),
        ("Gemini returned HTTP 429", "CHALLENGED"),
        ("Stealth HTTP relay encountered upstream challenge or timeout", "CHALLENGED"),
        ("Gemini upstream error: ConnectError", "UNKNOWN"),
        ("Failed to extract chat text from Gemini stream", "UNKNOWN"),
    ],
)
def test_failure_classification_is_conservative(detail, expected):
    assert server.classify_failure(HTTPException(502, detail))[0] == expected


def test_unknown_state_is_never_invented_from_a_bad_state_name():
    server.note_session("duck", "definitely-broken")
    assert server.session_snapshot()["duck"]["state"] == "UNKNOWN"


def test_no_cookie_value_ever_reaches_the_snapshot():
    server.relay_engine._cookies = {"__Secure-1PSID": "SECRET-COOKIE-VALUE"}
    try:
        rendered = str(server.session_snapshot())
    finally:
        server.relay_engine._cookies = {}
    assert "SECRET-COOKIE-VALUE" not in rendered
    assert "cookie_present" in rendered


def test_snapshot_reads_no_vault(tmp_path, monkeypatch):
    """`/health` is polled by the platform; it must not touch Infisical or disk."""
    def explode(*_args, **_kwargs):
        raise AssertionError("/health must not perform vault I/O")

    monkeypatch.setattr(server.relay_engine, "get_cookies", explode)
    monkeypatch.setattr(server.relay_engine, "fetch_cookies_from_infisical", explode)
    assert TestClient(server.app).get("/health").status_code == 200
