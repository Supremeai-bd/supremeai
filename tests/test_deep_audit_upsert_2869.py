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
    """HTTP-ব্যর্থতায় (যেমন 403 rate-limit str) raw বডি-সহ লগ; কোনো ক্র্য্যাশ নেই।"""
    with patch.object(pda, "http", return_value=(403, "rate limit exceeded")), \
         patch.object(pda, "find_tracker", return_value=2483), \
         patch.object(pda, "existing_issue_for", return_value=None):
        created = pda.upsert_issues([FINDING], "report-body")
    assert created == []
    out = capsys.readouterr().out
    assert "issue create FAILED HTTP 403" in out
    assert "rate limit exceeded" in out
