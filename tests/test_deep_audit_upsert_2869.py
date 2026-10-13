"""চুক্তি-টেস্ট (#2869): platform_deep_audit.upsert_issues — http() str-response ক্র্যাশ-প্রমাণ।

বাংলা নোট: http() helper সবসময় raw body str রিটার্ন করে; upsert_issues-এর দুটি
কল-সাইট আগে dict ধরে চলত — প্রথম সফল issue-creation-এই AttributeError-এ মৃত্যু
(নাইটলি-অপস রান 36846145557-এ প্রমাণিত)। এই টেস্ট str ও JSON উভয় রেসপন্স-পথে
no-crash + graceful-log + সঠিক created-রিটার্ন আইন করে।
"""
import importlib.util
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "platform_deep_audit.py"
_spec = importlib.util.spec_from_file_location("pda_2869", SCRIPT)
pda = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pda)

FINDING = {
    "ok": False,
    "platform": "groq",
    "check": "models",
    "category": "AUTH_INVALID",
    "severity": "P1",
    "fp": "cafebabe2869",
    "detail": "HTTP 401: Invalid API Key",
    "remediation": "key রোটেট করে vault আপডেট করুন",
    "note": None,
}


def test_str_response_does_not_crash_and_logs_graceful(capsys):
    """প্রি-ফিক্স: AttributeError ক্র্যাশ। পোস্ট-ফিক্স: created == [] + FAILED-লগ।"""
    with patch.object(pda, "http", return_value=(201, "<html>non-json body</html>")), \
         patch.object(pda, "find_tracker", return_value=2483), \
         patch.object(pda, "existing_issue_for", return_value=None):
        created = pda.upsert_issues([FINDING], "report-body")
    assert created == []
    out = capsys.readouterr().out
    assert "tracker #2483 updated" in out
    assert "issue create FAILED HTTP 201" in out


def test_json_response_returns_issue_number(capsys):
    """সুখ-পথ: JSON বডি পার্স হয়ে created-এ number যায় (রিগ্রেশন-গার্ড)।"""
    with patch.object(pda, "http", return_value=(201, '{"number": 42}')), \
         patch.object(pda, "find_tracker", return_value=2483), \
         patch.object(pda, "existing_issue_for", return_value=None):
        created = pda.upsert_issues([FINDING], "report-body")
    assert created == [42]
    assert "#42" in capsys.readouterr().out


def test_tracker_creation_branch_survives_str_response(capsys):
    """ট্র্যাকার-তৈরির ব্রাঞ্চও (~line 681) str-response-এ ক্র্যাশ করবে না; লুপ চলতেই থাকবে।"""
    with patch.object(pda, "http", return_value=(201, "raw-str-not-json")), \
         patch.object(pda, "find_tracker", return_value=None), \
         patch.object(pda, "existing_issue_for", return_value=None):
        created = pda.upsert_issues([FINDING], "report-body")
    out = capsys.readouterr().out
    assert "tracker" in out.lower()
    assert "issue create FAILED HTTP 201" in out
    assert created == []


def test_error_status_still_logged_with_raw_body(capsys):
    """HTTP-ব্যর্থতায় (যেমন 403 rate-limit str) raw বডি-সহ লগ; কোনো ক্র্যাশ নেই।"""
    with patch.object(pda, "http", return_value=(403, "rate limit exceeded")), \
         patch.object(pda, "find_tracker", return_value=2483), \
         patch.object(pda, "existing_issue_for", return_value=None):
        created = pda.upsert_issues([FINDING], "report-body")
    assert created == []
    out = capsys.readouterr().out
    assert "issue create FAILED HTTP 403" in out
    assert "rate limit exceeded" in out


# ── #46/#26: recovery auto-close চুক্তি ────────────────────────────────────────
PASSED_UPSTASH = {
    "ok": True,
    "platform": "upstash",
    "check": "ping[primary]",
    "category": None,
    "severity": None,
    "fp": "feedface4600",
    "detail": "HTTP 200 PONG",
    "remediation": "",
    "note": None,
}
SKIPPED_UPSTASH = {**PASSED_UPSTASH, "ok": None, "detail": "no REST creds in vault — account absent"}
FAILED_UPSTASH = {**PASSED_UPSTASH, "ok": False, "detail": "HTTP 403"}


def _close_calls_factory(comment_status: int, close_status: int):
    """method → status; calls-তালিকায় (method, url, positional-args, kwargs) রেকর্ড।"""
    calls: list[tuple] = []

    def fake(method, url, *a, **kw):
        calls.append((method, url, a, kw))
        if method == "POST":
            return comment_status, '{"id": 1}'
        return close_status, '{"number": 46}'

    return fake, calls


def test_verified_pass_closes_open_issue():
    """ok=True (verified pass) → recovery-comment + PATCH close; closed-তালিকায় number।"""
    fake, calls = _close_calls_factory(201, 200)
    with patch.object(pda, "http", side_effect=fake), \
         patch.object(pda, "gh_search_issues", return_value=[{"number": 46}]):
        closed = pda.close_recovered_findings([PASSED_UPSTASH], "https://github.example/actions/runs/1")
    assert closed == [46]
    assert calls[0][0] == "POST" and "/comments" in calls[0][1]
    assert calls[1][0] == "PATCH"
    # ৪র্থ positional arg = body (http(method, url, headers, body))
    assert calls[1][2][1] == {"state": "closed", "state_reason": "completed"}


def test_skipped_or_failed_never_triggers_close():
    """ok=None (skip) ও ok=False — কোনো search/close কলই নয় (fail-honest)।

    বাংলা: creds-অভাবে check skip হলে সেটা recovery নয়; পুরনো issue খোলা থাকে।
    """
    with patch.object(pda, "gh_search_issues") as search_mock, \
         patch.object(pda, "http") as http_mock:
        closed = pda.close_recovered_findings([SKIPPED_UPSTASH, FAILED_UPSTASH], "")
    assert closed == []
    search_mock.assert_not_called()
    http_mock.assert_not_called()


def test_empty_findings_no_close():
    """কোনো ok=True নেই → early-exit-এ পূর্বে early-return (কোনো কল নয়)।"""
    with patch.object(pda, "gh_search_issues") as search_mock, \
         patch.object(pda, "http") as http_mock:
        assert pda.close_recovered_findings([], "") == []
    search_mock.assert_not_called()
    http_mock.assert_not_called()


def test_comment_failure_blocks_close():
    """recovery-comment ব্যর্থ (403) → close PATCH কখনো চেষ্টা হয় না (আংশিক-প্রমাণ নয়)।"""
    fake, calls = _close_calls_factory(403, 200)
    with patch.object(pda, "http", side_effect=fake), \
         patch.object(pda, "gh_search_issues", return_value=[{"number": 46}]):
        closed = pda.close_recovered_findings([PASSED_UPSTASH], "")
    assert closed == []
    assert [c[0] for c in calls] == ["POST"], "শুধু comment-চেষ্টা; PATCH নয়"
