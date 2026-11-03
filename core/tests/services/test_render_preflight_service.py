# tests/services/test_render_preflight_service.py
"""Coverage ramp for services/render_preflight_service.py (0% -> high).

The service is the Render deploy-gate orchestrator: account status shaping,
cooldown retention, Render API usage calculation with bounded backoff,
preflight aggregation, manual admin override, and scheduled rechecks.

Strategy (wire-first — no owner code touched):
- the REAL RenderPreflightStore runs on a tmp_path SQLite file (honest
  persistence round-trips incl. event audit rows);
- the only external boundary, urllib.request.urlopen, is monkeypatched with
  scripted responders (JSON payloads / HTTPError / network failures).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import backend.services.render_preflight_service as rps
from backend.core.contracts.render_preflight_store import RenderPreflightStore

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


class FakeResponse:
    """Minimal context-manager response returning canned JSON bytes."""

    def __init__(self, payload: Any):
        self._payload = payload

    def read(self) -> bytes:
        import json

        raw = self._payload
        if isinstance(raw, (dict, list)):
            raw = json.dumps(raw).encode("utf-8")
        return raw

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def install_urlopen(monkeypatch, responder) -> list[tuple[str, dict, int | None]]:
    """Swap urllib.request.urlopen for a scripted responder; record calls."""
    calls: list[tuple[str, dict, int | None]] = []

    def fake_urlopen(req, timeout=None):
        calls.append(
            (
                req.full_url,
                {k.lower(): v for k, v in req.header_items()},
                timeout,
            )
        )
        result = responder(req)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def ok_response(deploys: list[Any]) -> FakeResponse:
    return FakeResponse(deploys)


def cur_month_ts(day: int, hour: int = 10, minute: int = 0, second: int = 0) -> str:
    now = datetime.now(UTC)
    return f"{now.year:04d}-{now.month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"


def prev_month_iso() -> str:
    now = datetime.now(UTC)
    prev = now.replace(day=1) - timedelta(days=1)
    return f"{prev.year:04d}-{prev.month:02d}-15T10:00:00Z"


def iso_in_days(days: float) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


@pytest.fixture
def store(tmp_path) -> RenderPreflightStore:
    return RenderPreflightStore(db_path=tmp_path / "preflight.db")


@pytest.fixture
def service(store) -> rps.RenderPreflightService:
    return rps.RenderPreflightService(store=store)


# ---------------------------------------------------------------------------
# calculate_deploy_usage_minutes (pure function)
# ---------------------------------------------------------------------------


def test_usage_empty_deploys_is_zero():
    assert rps.calculate_deploy_usage_minutes([]) == 0.0


def test_usage_single_current_month_deploy_minutes():
    deploys = [
        {
            "deploy": {
                "createdAt": cur_month_ts(3, 10, 0, 0),
                "finishedAt": cur_month_ts(3, 10, 30, 0),
            }
        }
    ]
    assert rps.calculate_deploy_usage_minutes(deploys) == 30.0


def test_usage_rounds_to_two_decimals():
    deploys = [
        {
            "deploy": {
                "createdAt": cur_month_ts(3, 10, 0, 0),
                "finishedAt": cur_month_ts(3, 10, 2, 3),
            }
        }
    ]
    # 123 seconds = 2.05 minutes
    assert rps.calculate_deploy_usage_minutes(deploys) == 2.05


def test_usage_accepts_bare_items_without_deploy_wrapper():
    deploys = [{"createdAt": cur_month_ts(3, 9, 0, 0), "finishedAt": cur_month_ts(3, 9, 15, 0)}]
    assert rps.calculate_deploy_usage_minutes(deploys) == 15.0


def test_usage_skips_deploys_missing_timestamps():
    deploys = [
        {"deploy": {"createdAt": None, "finishedAt": cur_month_ts(3, 10, 0, 0)}},
        {"deploy": {"createdAt": cur_month_ts(3, 10, 0, 0)}},
        {"deploy": {}},
    ]
    assert rps.calculate_deploy_usage_minutes(deploys) == 0.0


def test_usage_excludes_previous_month_and_other_year():
    deploys = [
        {"deploy": {"createdAt": prev_month_iso(), "finishedAt": prev_month_iso()}},
        {"deploy": {"createdAt": "2020-01-05T10:00:00Z", "finishedAt": "2020-01-05T11:00:00Z"}},
    ]
    assert rps.calculate_deploy_usage_minutes(deploys) == 0.0


def test_usage_skips_malformed_timestamps():
    deploys = [
        {"deploy": {"createdAt": "not-a-timestamp", "finishedAt": cur_month_ts(3, 11, 0, 0)}},
        {"deploy": {"createdAt": cur_month_ts(3, 10, 0, 0), "finishedAt": "13/45/2026"}},
    ]
    assert rps.calculate_deploy_usage_minutes(deploys) == 0.0


def test_usage_clamps_negative_durations_to_zero():
    deploys = [
        {
            "deploy": {
                "createdAt": cur_month_ts(5, 12, 0, 0),
                "finishedAt": cur_month_ts(5, 11, 0, 0),
            }
        },
    ]
    assert rps.calculate_deploy_usage_minutes(deploys) == 0.0


def test_usage_sums_multiple_valid_deploys():
    deploys = [
        {
            "deploy": {
                "createdAt": cur_month_ts(1, 9, 0, 0),
                "finishedAt": cur_month_ts(1, 9, 20, 0),
            }
        },
        {"createdAt": cur_month_ts(2, 9, 0, 0), "finishedAt": cur_month_ts(2, 9, 10, 30)},
        {"deploy": {"createdAt": prev_month_iso(), "finishedAt": prev_month_iso()}},
    ]
    assert rps.calculate_deploy_usage_minutes(deploys) == 30.5


# ---------------------------------------------------------------------------
# get_account_status (read-only shaping)
# ---------------------------------------------------------------------------


def test_get_account_status_unknown_role_payload(service):
    res = service.get_account_status("ghost-role")
    assert res["status"] == "unknown"
    assert res["reason_code"] == "unregistered_account"
    assert res["safe_build_minutes"] == 450.0
    assert res["usage_minutes"] is None
    assert res["source"] == "cached"


def test_get_account_status_known_role_cached_source(service, store):
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-1", status="ready", usage_minutes=12.5
    )
    res = service.get_account_status("builder")
    assert res["account_role"] == "builder"
    assert res["status"] == "ready"
    assert res["usage_minutes"] == 12.5
    assert res["source"] == "cached"


def test_get_account_status_manual_override_source(service, store):
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-1", status="cooldown"
    )
    store.set_manual_override("builder", "admin-1", "deploy emergency")
    res = service.get_account_status("builder")
    assert res["status"] == "ready"
    assert res["source"] == "manual_override"


def test_get_account_status_no_role_lists_all(service, store):
    store.upsert_account_and_record_event(account_role="beta", service_id="svc-b", status="ready")
    store.upsert_account_and_record_event(account_role="alpha", service_id="svc-a", status="error")
    res = service.get_account_status()
    assert isinstance(res, list)
    assert [a["account_role"] for a in res] == ["alpha", "beta"]  # store orders by role
    assert {a["status"] for a in res} == {"ready", "error"}


# ---------------------------------------------------------------------------
# refresh_account_status — credential / retention guards
# ---------------------------------------------------------------------------


def test_refresh_missing_credentials_records_unknown(service, store):
    res = service.refresh_account_status("fresh-role")
    assert res["status"] == "unknown"
    assert res["reason_code"] == "missing_credentials"
    assert res["service_id"] == "unconfigured"
    events = store.get_events("fresh-role")
    assert events and events[0]["event_type"] == "check"


def test_refresh_reuses_existing_service_id_and_sends_auth_header(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-known", status="error"
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    res = service.refresh_account_status("builder", api_key="rk_live")
    assert res["status"] == "ready"
    assert "services/svc-known/deploys" in calls[0][0]
    assert "limit=100" in calls[0][0]
    assert calls[0][1].get("authorization") == "Bearer rk_live"
    assert calls[0][2] == 15


def test_refresh_missing_api_key_records_unknown(service, monkeypatch):
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    res = service.refresh_account_status("builder", service_id="svc-x")
    assert res["reason_code"] == "missing_credentials"
    assert calls == []


def test_refresh_active_cooldown_retained_without_force(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-1", status="cooldown", recheck_at=iso_in_days(5)
    )
    before = store.get_account("builder")
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k", force=False)
    assert res == before  # untouched record
    assert calls == []  # no API call while cooling down


def test_refresh_expired_cooldown_proceeds_to_live_recheck(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-1", status="cooldown", recheck_at=iso_in_days(-1)
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "ready"
    assert len(calls) == 1


def test_refresh_cooldown_without_recheck_at_proceeds(service, store, monkeypatch):
    """A cooldown record with NO recheck_at cannot be retained -> live recheck."""
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-1", status="cooldown", recheck_at=None
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "ready"
    assert len(calls) == 1


def test_refresh_unparsable_recheck_at_proceeds_with_warning(service, store, monkeypatch, caplog):
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-1", status="cooldown", recheck_at="garbage"
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    with caplog.at_level("WARNING"):
        res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "ready"
    assert len(calls) == 1
    assert any("Unparsable recheck_at" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# refresh_account_status — Render API outcomes
# ---------------------------------------------------------------------------


def http_err(code: int, reason: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.render.com", code, reason, None, None)


def test_refresh_http_429_starts_default_cooldown(service, store, monkeypatch):
    calls = install_urlopen(monkeypatch, lambda req: http_err(429, "Too Many Requests"))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "cooldown"
    assert res["reason_code"] == "build_time_limit"
    assert res["retry_count"] == 1  # increment_retry
    assert len(calls) == 1  # exactly one Render API attempt was made
    assert res["last_error"] == "HTTP 429: Too Many Requests"
    recheck = datetime.fromisoformat(res["recheck_at"].replace("Z", "+00:00"))
    delta_days = (recheck - datetime.now(UTC)).total_seconds() / 86400
    assert 9.5 < delta_days < 10.5
    assert store.get_events("builder")[0]["event_type"] == "limit_detected"


def test_refresh_http_reason_containing_limit_also_cooldowns(service, monkeypatch):
    install_urlopen(monkeypatch, lambda req: http_err(403, "Rate Limit Exceeded"))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "cooldown"
    assert res["reason_code"] == "build_time_limit"


def test_refresh_other_http_error_is_api_error_without_cooldown(service, monkeypatch):
    install_urlopen(monkeypatch, lambda req: http_err(500, "Internal Server Error"))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "error"
    assert res["reason_code"] == "api_error"
    assert res["recheck_at"] is None
    assert res["last_error"] == "HTTP 500: Internal Server Error"


def test_refresh_network_failure_is_api_unavailable_and_truncated(service, monkeypatch):
    class Boom(Exception):
        pass

    long_msg = "connection reset while dialing " + "x" * 200
    install_urlopen(monkeypatch, lambda req: Boom(long_msg))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "unknown"
    assert res["reason_code"] == "api_unavailable"
    assert len(res["last_error"]) <= 160
    assert res["last_error"].startswith("connection reset while dialing")


def test_refresh_usage_over_cap_cooldowns_with_payload(service, monkeypatch):
    deploys = [
        {
            "deploy": {
                "createdAt": cur_month_ts(1, 9, 0, 0),
                "finishedAt": cur_month_ts(1, 18, 0, 0),
            }
        },
        {
            "deploy": {
                "createdAt": cur_month_ts(2, 9, 0, 0),
                "finishedAt": cur_month_ts(2, 9, 30, 0),
            }
        },
    ]
    install_urlopen(monkeypatch, lambda req: ok_response(deploys))
    res = service.refresh_account_status(
        "builder", service_id="svc-1", api_key="k", safe_build_minutes=450.0
    )
    assert res["status"] == "cooldown"
    assert res["reason_code"] == "build_time_limit"
    assert res["usage_minutes"] == 570.0  # 9h + 30m in the current month
    assert res["last_render_payload"] == {"deploys_count": 2, "calculated_usage": 570.0}


def test_refresh_over_cap_backoff_grows_with_retry_count(service, store, monkeypatch):
    deploys = [
        {
            "deploy": {
                "createdAt": cur_month_ts(1, 9, 0, 0),
                "finishedAt": cur_month_ts(1, 18, 0, 0),
            }
        },
    ]
    install_urlopen(monkeypatch, lambda req: ok_response(deploys))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k", force=False)
    assert res["status"] == "cooldown"
    assert res["retry_count"] == 1
    recheck = datetime.fromisoformat(res["recheck_at"].replace("Z", "+00:00"))
    delta = (recheck - datetime.now(UTC)).total_seconds() / 86400
    assert 9.5 < delta < 10.5  # retry 0 -> default 10 days


def test_refresh_over_cap_backoff_thirty_day_ceiling(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="builder",
        service_id="svc-1",
        status="error",
        retry_count=3,
    )
    deploys = [
        {
            "deploy": {
                "createdAt": cur_month_ts(1, 9, 0, 0),
                "finishedAt": cur_month_ts(1, 18, 0, 0),
            }
        },
    ]
    install_urlopen(monkeypatch, lambda req: ok_response(deploys))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "cooldown"
    assert res["retry_count"] == 4
    recheck = datetime.fromisoformat(res["recheck_at"].replace("Z", "+00:00"))
    delta = (recheck - datetime.now(UTC)).total_seconds() / 86400
    # min(10 * 2**3, 30) = 30-day ceiling
    assert 29.5 < delta < 30.5


def test_refresh_under_cap_is_ready_and_clears_recheck(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="builder", service_id="svc-1", status="cooldown", recheck_at=iso_in_days(-1)
    )
    install_urlopen(monkeypatch, lambda req: ok_response([]))
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "ready"
    assert res["recheck_at"] is None
    assert res["retry_count"] == 0
    assert store.get_events("builder")[0]["event_type"] == "ready"


def test_refresh_handles_dict_payload_with_deploys_key(service, monkeypatch):
    install_urlopen(
        monkeypatch,
        lambda req: ok_response(
            {
                "deploys": [
                    {"createdAt": cur_month_ts(1, 9, 0, 0), "finishedAt": cur_month_ts(1, 9, 5, 0)}
                ]
            }
        ),
    )
    res = service.refresh_account_status("builder", service_id="svc-1", api_key="k")
    assert res["status"] == "ready"
    assert res["usage_minutes"] == 5.0


# ---------------------------------------------------------------------------
# get_deploy_preflight (aggregation)
# ---------------------------------------------------------------------------


def test_preflight_empty_store_blocks_build(service):
    res = service.get_deploy_preflight()
    assert res["build_allowed"] is False  # zero accounts is NOT a pass
    assert res["status"] == "blocked"
    assert res["blocked_accounts"] == []
    assert res["accounts"] == []


def test_preflight_all_ready_allows_build(service, store):
    store.upsert_account_and_record_event(account_role="a", service_id="s1", status="ready")
    store.upsert_account_and_record_event(account_role="b", service_id="s2", status="ready")
    res = service.get_deploy_preflight()
    assert res["build_allowed"] is True
    assert res["status"] == "ready"
    assert res["blocked_accounts"] == []


def test_preflight_blocked_roles_listed_with_earliest_recheck(service, store):
    store.upsert_account_and_record_event(account_role="a", service_id="s1", status="ready")
    store.upsert_account_and_record_event(
        account_role="b", service_id="s2", status="cooldown", recheck_at=iso_in_days(9)
    )
    store.upsert_account_and_record_event(
        account_role="c", service_id="s3", status="cooldown", recheck_at=iso_in_days(2)
    )
    res = service.get_deploy_preflight()
    assert res["blocked_accounts"] == ["b", "c"]
    assert res["status"] == "blocked"
    # earliest recheck wins regardless of role order
    earliest = datetime.fromisoformat(res["recheck_at"].replace("Z", "+00:00"))
    assert earliest < datetime.now(UTC) + timedelta(days=3)


def test_preflight_required_roles_filter(service, store):
    store.upsert_account_and_record_event(account_role="a", service_id="s1", status="ready")
    store.upsert_account_and_record_event(account_role="b", service_id="s2", status="cooldown")
    res = service.get_deploy_preflight(required_roles=["a"])
    assert res["build_allowed"] is True  # b not required -> does not block
    res2 = service.get_deploy_preflight(required_roles=["b"])
    assert res2["build_allowed"] is False
    assert res2["blocked_accounts"] == ["b"]


def test_preflight_summary_surfaces_override_and_reason_fallback(service, store):
    store.upsert_account_and_record_event(
        account_role="a",
        service_id="s1",
        status="ready",
        reason_message="Usage 12m < cap 450m",
    )
    store.set_manual_override("a", "admin", "hotfix window")
    res = service.get_deploy_preflight()
    acc = res["accounts"][0]
    assert acc["manual_override"] is True
    assert acc["reason"] == "Usage 12m < cap 450m"  # reason_code None -> message fallback
    assert acc["status"] == "ready"


# ---------------------------------------------------------------------------
# manual_override (admin action)
# ---------------------------------------------------------------------------


def test_manual_override_sets_ready_and_records_event(service, store):
    store.upsert_account_and_record_event(account_role="a", service_id="s1", status="cooldown")
    res = service.manual_override("a", approved_by="admin-7", reason="approved deployment")
    assert res["status"] == "ready"
    assert res["manual_override"] is True
    assert res["manual_override_by"] == "admin-7"
    assert res["manual_override_reason"] == "approved deployment"
    events = store.get_events("a")
    assert events[0]["event_type"] == "manual_override"
    assert events[0]["old_status"] == "cooldown"


def test_manual_override_unknown_role_raises(service):
    with pytest.raises(ValueError, match="does not exist"):
        service.manual_override("ghost", approved_by="admin", reason="nope")


# ---------------------------------------------------------------------------
# run_scheduled_rechecks
# ---------------------------------------------------------------------------


def test_scheduled_rechecks_skips_accounts_without_recheck(service, store, monkeypatch):
    store.upsert_account_and_record_event(account_role="a", service_id="s1", status="ready")
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    assert service.run_scheduled_rechecks({"a": "k"}) == []
    assert calls == []


def test_scheduled_rechecks_skips_future_rechecks(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="a", service_id="s1", status="cooldown", recheck_at=iso_in_days(4)
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    assert service.run_scheduled_rechecks({"a": "k"}) == []
    assert calls == []


def test_scheduled_rechecks_skips_missing_api_key(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="a", service_id="s1", status="cooldown", recheck_at=iso_in_days(-1)
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    assert service.run_scheduled_rechecks({}) == []
    assert calls == []


def test_scheduled_rechecks_force_refreshes_due_accounts(service, store, monkeypatch):
    store.upsert_account_and_record_event(
        account_role="a", service_id="s1", status="cooldown", recheck_at=iso_in_days(-1)
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    results = service.run_scheduled_rechecks({"a": "key-a"})
    assert len(results) == 1
    assert results[0]["status"] == "ready"
    assert len(calls) == 1


def test_scheduled_rechecks_corrupt_recheck_does_not_abort_batch(service, store, monkeypatch):
    # corrupt record first (alphabetical order), healthy record second
    store.upsert_account_and_record_event(
        account_role="a-bad", service_id="s1", status="cooldown", recheck_at="not-a-date"
    )
    store.upsert_account_and_record_event(
        account_role="z-good", service_id="s2", status="cooldown", recheck_at=iso_in_days(-1)
    )
    calls = install_urlopen(monkeypatch, lambda req: ok_response([]))
    results = service.run_scheduled_rechecks({"a-bad": "k1", "z-good": "k2"})
    assert [r["account_role"] for r in results] == ["z-good"]
    # only the healthy account reached the API; the corrupt one was skipped
    assert len(calls) == 1
    assert "services/s2/deploys" in calls[0][0]  # z-good's service_id


# ---------------------------------------------------------------------------
# constructor default store path
# ---------------------------------------------------------------------------


def test_service_default_store_uses_registered_default(tmp_path, monkeypatch):
    from backend.core.contracts import render_preflight_store as store_mod

    monkeypatch.setattr(store_mod, "DEFAULT_DB_PATH", tmp_path / "default.db")
    svc = rps.RenderPreflightService()
    assert str(svc.store.db_path) == str(tmp_path / "default.db")
    svc.store._conn.close()
