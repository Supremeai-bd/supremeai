# বাংলা মন্তব্য: #3088 §3 — universal fingerprint + duplicate-guard টেস্ট।
"""issue_fingerprint.py — fingerprint স্থিতিশীলতা, স্বাভাবিকীকরণ, active/closed dedup।"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "agents"))

from issue_fingerprint import (  # noqa: E402
    DEFAULT_CLOSED_WINDOW_DAYS,
    duplicate_guard,
    extract_fingerprint,
    find_active_duplicate,
    find_recently_closed_duplicate,
    fingerprint,
    marker,
    normalize_token,
    prepend_marker,
)


# ── fingerprint composition + normalization (#3088 §3) ───────────────────────

def test_fingerprint_stable():
    a = fingerprint("pipeline", "Register race reconciliation", "scripts/ci/register.py", "concurrency")
    b = fingerprint("PIPELINE", "register  race   reconciliation!", "scripts/ci/register.py", "concurrency")
    assert a == b and len(a) == 12


def test_fingerprint_differs_by_component():
    base = fingerprint("pipeline", "same problem", "scope", "concurrency")
    assert base != fingerprint("security", "same problem", "scope", "concurrency")
    assert base != fingerprint("pipeline", "different problem", "scope", "concurrency")
    assert base != fingerprint("pipeline", "same problem", "other-scope", "concurrency")
    assert base != fingerprint("pipeline", "same problem", "scope", "logic")


def test_normalize_token_strips_punctuation_and_case():
    assert normalize_token("Hello,   World!!") == "hello world"
    assert normalize_token("বাংলা টেক্সট ঠিক থাকে") == "বাংলা টেক্সট ঠিক থাকে"


def test_marker_roundtrip():
    fp = fingerprint("governance", "p", "s", "logic")
    assert extract_fingerprint(marker(fp)) == fp
    assert extract_fingerprint(f"leading text\n{marker(fp)}\ntrailing") == fp
    assert extract_fingerprint("no marker here") is None


def test_prepend_marker_idempotent():
    fp = fingerprint("governance", "p", "s", "logic")
    once = prepend_marker("body", fp)
    twice = prepend_marker(once, fp)
    assert once == twice  # দ্বিতীয়বার মার্কার জন্মাবে না


# ── active/closed duplicate lookup (FakeGh) ─────────────────────────────────

class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _issue(num, body, closed_at=None):
    d = {"number": num, "title": f"t{num}", "labels": [], "body": body}
    if closed_at:
        d["closedAt"] = closed_at
    return d


def test_find_active_duplicate_group_scoped(monkeypatch):
    fp = fingerprint("pipeline", "race in register", "register.py", "concurrency")
    seen_calls = []

    def fake_run(cmd, *a, **k):
        seen_calls.append(cmd)
        label = cmd[cmd.index("--label") + 1] if "--label" in cmd else None
        if label == "group:pipeline":
            payload = json.dumps([_issue(500, marker(fp) + "\nbody")])
        else:
            payload = "[]"  # universal fallback লাগবেই না — group-hit এ থামে
        return _FakeCompleted(payload)

    monkeypatch.setattr("issue_fingerprint.subprocess.run", fake_run)
    hit = find_active_duplicate(fp, "pipeline")
    assert hit and hit["number"] == 500
    assert len(seen_calls) == 1  # group-first: universal-scan হয়নি


def test_find_active_duplicate_fallback_universal(monkeypatch):
    fp = fingerprint("security", "key rotation", "vault", "stale-state")

    def fake_run(cmd, *a, **k):
        label = cmd[cmd.index("--label") + 1] if "--label" in cmd else None
        if label == "group:security":
            return _FakeCompleted("[]")
        return _FakeCompleted(json.dumps([_issue(700, f"prefix\n{marker(fp)}")]))

    monkeypatch.setattr("issue_fingerprint.subprocess.run", fake_run)
    hit = find_active_duplicate(fp, "security")
    assert hit and hit["number"] == 700


def test_find_recently_closed_duplicate_window(monkeypatch):
    fp = fingerprint("reliability", "watchdog blind", "funnel", "wiring")
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    stale = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")

    def fake_run(cmd, *a, **k):
        return _FakeCompleted(json.dumps([
            _issue(800, marker(fp), closed_at=stale),   # window-বাইরে → উপেক্ষা
            _issue(801, marker(fp), closed_at=fresh),   # window-ভিতরে → hit
        ]))

    monkeypatch.setattr("issue_fingerprint.subprocess.run", fake_run)
    hit = find_recently_closed_duplicate(fp, DEFAULT_CLOSED_WINDOW_DAYS)
    assert hit and hit["number"] == 801


def test_find_recently_closed_duplicate_none(monkeypatch):
    fp = fingerprint("product", "ux polish", "ui", "logic")
    monkeypatch.setattr(
        "issue_fingerprint.subprocess.run",
        lambda *a, **k: _FakeCompleted("[]"),
    )
    assert find_recently_closed_duplicate(fp, 7) is None


# ── duplicate_guard verdicts (#3088 §3 — creation-সিদ্ধান্ত) ──────────────────

def test_guard_blocks_on_active_duplicate(monkeypatch):
    monkeypatch.setattr(
        "issue_fingerprint.find_active_duplicate",
        lambda f, g=None, repo_dir=None, limit=100: {"number": 900, "title": "t", "state": "open"},
    )
    verdict = duplicate_guard("pipeline", "dup problem", "s", "logic")
    assert verdict.action == "update_existing" and verdict.blocked
    assert verdict.duplicate_of == 900


def test_guard_blocks_on_recently_closed(monkeypatch):
    monkeypatch.setattr("issue_fingerprint.find_active_duplicate", lambda *a, **k: None)
    monkeypatch.setattr(
        "issue_fingerprint.find_recently_closed_duplicate",
        lambda f, w=7, repo_dir=None, limit=100: {"number": 901, "title": "t", "closed_at": "x"},
    )
    verdict = duplicate_guard("pipeline", "closed problem", "s", "logic")
    assert verdict.action == "suppressed_closed" and verdict.blocked
    assert verdict.duplicate_of == 901


def test_guard_allows_when_clear(monkeypatch):
    monkeypatch.setattr("issue_fingerprint.find_active_duplicate", lambda *a, **k: None)
    monkeypatch.setattr("issue_fingerprint.find_recently_closed_duplicate", lambda *a, **k: None)
    verdict = duplicate_guard("governance", "brand new", "s", "wiring")
    assert verdict.action == "create" and not verdict.blocked


def test_guard_fail_open_when_lookup_crashes(monkeypatch):
    # বাংলা মন্তব্য: অনিশ্চিত state-এ creation-পথ fail-open (advisory) —
    # চালু কাজ আটকাবে না; dedup-জালের দায় পরবর্তী স্ক্যানে।
    def boom(*a, **k):
        raise RuntimeError("api down")

    monkeypatch.setattr("issue_fingerprint.find_active_duplicate", boom)
    monkeypatch.setattr("issue_fingerprint.find_recently_closed_duplicate", boom)
    verdict = duplicate_guard("pipeline", "x", "y", "z")
    assert verdict.action == "create" and not verdict.blocked
