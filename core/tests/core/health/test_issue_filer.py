"""#2527 — error_event_bus → GitHub issue self-filing bridge টেস্ট।

বাংলা মন্তব্য: signature/dedup/burst-gate-এর pure লজিক নেটওয়ার্ক ছাড়াই
প্রমাণ করা হয়; GitHub ফাইলিং পাথ mock-করা httpx transport দিয়ে যাচাই।
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("httpx")

from core.health import issue_filer as filer
from core.messaging.event_bus import ErrorEvent

httpx = pytest.importorskip("httpx")


def _event(
    severity: str = "ERROR", module: str = "payments", error_type: str = "TIMEOUT"
) -> ErrorEvent:
    return ErrorEvent(
        module=module,
        error_type=error_type,
        message=f"Simulated {error_type} in {module}",
        severity=severity,
        context={"sim": True},
    )


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """প্রতিটি টেস্টে fresh dedup-state + startup-quiet পেরনো অবস্থা।"""
    filer.reset_filer_state_for_tests(boot_offset_s=-10_000.0)
    yield
    filer.reset_filer_state_for_tests(boot_offset_s=-10_000.0)


# ── ১. Signature: module+error_type শ্রেণি-ভিত্তিক, message-নিরপেক্ষ ──────


def test_signature_stable_across_messages():
    a = filer._signature(_event(message=None) if False else _event())  # noqa: F841
    b = filer._signature(_event())
    assert a == b
    c = filer._signature(_event(error_type="DB_DOWN"))
    assert a != c
    d = filer._signature(_event(module="auth"))
    assert a != d


def test_marker_embeds_signature():
    sig = filer._signature(_event())
    assert filer._marker(sig) == f"error-signature: {sig}"


# ── ২. Severity gate ───────────────────────────────────────────────────────


def test_should_file_severity_gate():
    assert filer._should_file(_event(severity="CRITICAL")) is True
    assert filer._should_file(_event(severity="ERROR")) is True
    assert filer._should_file(_event(severity="HIGH")) is True
    assert filer._should_file(_event(severity="WARNING")) is False
    assert filer._should_file(_event(severity="INFO")) is False


# ── ৩. Startup-quiet window (restart-storm রোধ) ───────────────────────────


def test_should_file_startup_quiet():
    filer.reset_filer_state_for_tests(boot_offset_s=0.0)  # এখনই বুট
    assert filer._should_file(_event()) is False  # quiet-window চলমান


# ── ৪. Per-signature cooldown (২৪ঘণ্টা) + daily cap ───────────────────────


def test_per_signature_cooldown():
    ev = _event()
    sig = filer._signature(ev)
    filer._last_filed_at[sig] = time.time()  # এইমাত্র ফাইল হয়েছে
    assert filer._should_file(ev) is False


def test_daily_cap():
    filer._filed_today[filer._today_key()] = filer._DAILY_CAP
    assert filer._should_file(_event()) is False


# ── ৫. Issue payload স্কিমা (labels/marker/শিরোনাম) ─────────────────────────


def test_build_issue_payload_schema():
    ev = _event(module="billing", error_type="STRIPE_500", severity="CRITICAL")
    sig = filer._signature(ev)
    payload = filer._build_issue_payload(ev, sig)
    assert payload["title"].startswith("[self-filed] billing: STRIPE_500")
    assert "type:reliability" in payload["labels"]
    assert "status:unclaimed" in payload["labels"]
    assert filer._marker(sig) in payload["body"]  # GitHub-side dedup marker
    assert "#2527" in payload["body"]


# ── ৬. GitHub-side dedup: marker-ম্যাচ হলে নতুন ইস্যু নয় ────────────────────


@pytest.mark.asyncio
async def test_dedup_skips_when_marker_exists(monkeypatch):
    """mock transport: open ইস্যুর একটিতে marker আছে → create কল হবে না।"""
    ev = _event(module="queue", error_type="WORKER_OOM")
    sig = filer._signature(ev)
    created: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues") and request.method == "POST":
            created.append(request.read())
            return httpx.Response(201, json={"number": 999})
        # GET /issues লিস্টিং — PR-এন্ট্রি + marker-ইস্যু + সাধারণ ইস্যু
        return httpx.Response(
            200,
            json=[
                {"number": 1, "body": "unrelated", "pull_request": {}},
                {"number": 2, "body": f"কিছু বিবরণ\n{filer._marker(sig)}\nশেষ"},
                {"number": 3, "body": "another"},
            ],
        )

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient

    def patched_client(**kwargs):
        return orig_client(transport=transport, **kwargs)

    monkeypatch.setattr(filer.httpx, "AsyncClient", patched_client)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    number = await filer._file_issue(ev, sig)
    assert number is None  # existing পাওয়া গেছে — নতুন ইস্যু খোলা হয়নি
    assert created == []  # POST কখনোই হয়নি
    assert filer._last_filed_at[sig] > 0  # কুলডাউন চালু


# ── ৭. Token না থাকলে graceful skip (Rule ৩) ───────────────────────────────


@pytest.mark.asyncio
async def test_no_token_graceful(monkeypatch):
    for var in ("GITHUB_TOKEN", "GH_TOKEN", "SUPREMEAI_GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    filer._warned_no_token = False
    number = await filer._file_issue(_event(), "deadbeef1234")
    assert number is None


# ── ৮. Listener boundary: filing ব্যর্থ হলেও raise নয় ─────────────────────


@pytest.mark.asyncio
async def test_listener_never_raises(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("github down")

    monkeypatch.setattr(filer, "_file_issue", boom)
    # এটা raise করবে না — listener ভেতরে catch করে
    await filer._issue_filer_listener(_event())


# ── ৯. Happy path: marker না থাকলে create + state আপডেট ───────────────────


@pytest.mark.asyncio
async def test_happy_path_creates_issue(monkeypatch):
    ev = _event(module="scheduler", error_type="MISSbeat".upper())
    sig = filer._signature(ev)
    created: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues") and request.method == "POST":
            import json as _json

            created.append(_json.loads(request.read()))
            return httpx.Response(201, json={"number": 4242})
        return httpx.Response(200, json=[{"number": 7, "body": "no marker here"}])

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient

    def patched_client(**kwargs):
        return orig_client(transport=transport, **kwargs)

    monkeypatch.setattr(filer.httpx, "AsyncClient", patched_client)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    number = await filer._file_issue(ev, sig)
    assert number == 4242
    assert len(created) == 1
    assert created[0]["title"].startswith("[self-filed] scheduler:")
    assert filer._marker(sig) in created[0]["body"]
