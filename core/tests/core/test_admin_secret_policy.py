"""P0 — Internal admin secret policy tests.

বাংলা: internal admin API-র X-Admin-Secret গেট আগে docs_password-এ
ফলব্যাক করত — ফলে পাবলিক রিপোর জানা "dev_password_only" প্রোডাকশনে
বৈধ অ্যাডমিন সিক্রেট হয়ে যেত। নতুন পলিসি:

1. আলাদা SUPREMEAI_ADMIN_SECRET ফিল্ড (>= ১২ অক্ষর, dev ফলব্যাক নয়,
   docs_password-এর সমান নয়) — production/staging বুটে fail-fast।
2. Runtime গেট fail-closed — কোনো docs_password ফলব্যাক নেই।
"""

import pytest
from fastapi import HTTPException, Request

from api.routes.internal import _require_admin
from core.config import Settings, settings

STRONG_SECRET = "unit-test-admin-secret-0123456789"
STRONG_DOCS_PASSWORD = "unit-test-docs-password-0123456789"


# ---------------------------------------------------------------------------
# Settings policy (admin_secret_ok)
# ---------------------------------------------------------------------------


def _make_settings(env: str, extra_env: dict | None = None) -> Settings:
    """Build a Settings instance with a controlled ENV and extra overrides."""
    import os
    from unittest.mock import patch

    env_overrides = {"ENV": env}
    env_overrides.update(extra_env or {})
    # বাংলা: বাইরের প্রসেস এনভ থেকে সংশ্লিষ্ট ভেরিয়েবল আইসোলেট করা।
    for var in ("SUPREMEAI_ADMIN_SECRET", "SUPREMEAI_DOCS_PASSWORD"):
        os.environ.pop(var, None)
    with patch.dict(os.environ, env_overrides, clear=False):
        return Settings()


def test_local_admin_secret_defaults_empty():
    s = _make_settings("local")
    assert s.supremeai_admin_secret.get_secret_value() == ""
    assert s.admin_secret_ok is False


def test_local_strong_admin_secret_is_ok():
    s = _make_settings("local", {"SUPREMEAI_ADMIN_SECRET": STRONG_SECRET})
    assert s.admin_secret_ok is True


def test_dev_fallback_admin_secret_never_ok():
    s = _make_settings("local", {"SUPREMEAI_ADMIN_SECRET": "dev_password_only"})
    assert s.admin_secret_ok is False


def test_short_admin_secret_not_ok():
    s = _make_settings("local", {"SUPREMEAI_ADMIN_SECRET": "short"})
    assert s.admin_secret_ok is False


def test_admin_secret_equal_to_docs_password_not_ok():
    # বাংলা: reuse নিষেধ — docs গেট ও admin গেট একই সিক্রেট শেয়ার
    # করলে একটার লিক মানেই দুটোর কম্প্রোমাইজ।
    same = STRONG_DOCS_PASSWORD
    s = _make_settings(
        "local",
        {
            "SUPREMEAI_ADMIN_SECRET": same,
            "SUPREMEAI_DOCS_PASSWORD": same,
        },
    )
    assert s.admin_secret_ok is False


def test_production_boot_policy_requires_strong_admin_secret():
    # বাংলা: রিয়েল বুটে config_validation ফেইল-ফাস্ট করে; এখানে
    # পলিসি প্রপার্টি লেভেলে যাচাই করা হচ্ছে (validate_all pytest-এ
    # স্কিপ করে — test_docs_exposure_policy.py-র মতোই)।
    s = _make_settings("production")
    assert s.admin_secret_ok is False


# ---------------------------------------------------------------------------
# Runtime gate (_require_admin) — fail-closed, no docs_password fallback
# ---------------------------------------------------------------------------


def _request_with_secret(value: str | None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if value is not None:
        headers.append((b"x-admin-secret", value.encode()))
    return Request(scope={"type": "http", "headers": headers})


def test_missing_server_secret_fails_closed_even_with_public_fallback_header(monkeypatch):
    # বাংলা: সার্ভারে সিক্রেট কনফিগার না থাকলে "dev_password_only"
    # হেডারও ৫০০ ছাড়া কিছুই পাবে না — পুরনো বাইপাস পথটি এখন বন্ধ।
    monkeypatch.setattr(settings, "supremeai_admin_secret", "", raising=False)
    with pytest.raises(HTTPException) as exc:
        _require_admin(_request_with_secret("dev_password_only"))
    assert exc.value.status_code == 500


def test_wrong_secret_rejected(monkeypatch):
    monkeypatch.setattr(settings, "supremeai_admin_secret", STRONG_SECRET, raising=False)
    with pytest.raises(HTTPException) as exc:
        _require_admin(_request_with_secret("not-the-right-secret"))
    assert exc.value.status_code == 403


def test_missing_header_rejected(monkeypatch):
    monkeypatch.setattr(settings, "supremeai_admin_secret", STRONG_SECRET, raising=False)
    with pytest.raises(HTTPException) as exc:
        _require_admin(_request_with_secret(None))
    assert exc.value.status_code == 403


def test_correct_secret_passes(monkeypatch):
    monkeypatch.setattr(settings, "supremeai_admin_secret", STRONG_SECRET, raising=False)
    # সঠিক সিক্রেট → কোনো exception নেই।
    _require_admin(_request_with_secret(STRONG_SECRET))


def test_docs_password_value_is_no_longer_a_valid_admin_secret(monkeypatch):
    # বাংলা: সার্ভারের admin সিক্রেট সেট থাকলেও docs_password-এর মান
    # আলাদা — docs পাসওয়ার্ড দিয়ে admin গেট পার হওয়া যাবে না।
    monkeypatch.setattr(settings, "supremeai_admin_secret", STRONG_SECRET, raising=False)
    with pytest.raises(HTTPException) as exc:
        _require_admin(_request_with_secret(STRONG_DOCS_PASSWORD))
    assert exc.value.status_code == 403
