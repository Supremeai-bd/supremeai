"""NightlyChaosAuditor (workers/chaos_worker.py) এর ইউনিট টেস্ট।

বাংলা: মডিউল-লেভেল কনস্ট্যান্ট ও NightlyChaosAuditor ইনিশিয়ালাইজেশন কভার করা হয়েছে।
Firestore db get_firestore_db মক করে ইনস্ট্যান্স তৈরির বিভিন্ন ব্রাঞ্চ (db None vs not None) যাচাই করা হয়েছে।
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from workers import chaos_worker


def test_server_error_threshold_constant():
    # বাংলা: সার্ভার এরর থ্রেশহোল্ড 500 — HTTP 5xx চিহ্নিত করতে ব্যবহৃত হয়
    assert chaos_worker.SERVER_ERROR_THRESHOLD == 500


def test_auditor_init_with_db(monkeypatch):
    # বাংলা মন্তব্য: NightlyChaosAuditor ইচ্ছাকৃতভাবে STAGING_REPLICA_URL না থাকলে
    # target_url খালি রাখে ও chaos audit disable করে (production safety) --
    # তাই এখানে explicit ভাবে সেট করে দিয়ে "http দিয়ে শুরু হয়" চেক করা হচ্ছে।
    monkeypatch.setenv("STAGING_REPLICA_URL", "https://staging.example.com")
    fake_db = MagicMock()
    with patch("workers.chaos_worker.get_firestore_db", return_value=fake_db):
        auditor = chaos_worker.NightlyChaosAuditor()
        assert auditor.db is fake_db
        assert auditor.gate_ref is not None
        assert auditor.target_url.startswith("http")


def test_auditor_init_without_db():
    with patch("workers.chaos_worker.get_firestore_db", return_value=None):
        auditor = chaos_worker.NightlyChaosAuditor()
        assert auditor.db is None
        assert auditor.gate_ref is None


def test_auditor_init_custom_target_url(monkeypatch):
    monkeypatch.setenv("STAGING_REPLICA_URL", "https://staging.example.com")
    with patch("workers.chaos_worker.get_firestore_db", return_value=None):
        auditor = chaos_worker.NightlyChaosAuditor()
        assert auditor.target_url == "https://staging.example.com"
