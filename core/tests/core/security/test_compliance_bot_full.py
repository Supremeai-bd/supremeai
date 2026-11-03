"""Full-coverage tests for core/security/audit/compliance_bot.py (Task 7 wave-2).

Covers ConsentRecord/GDPRChecker/DigitalSecurityActChecker/ConsentManager/
DataRetentionPolicy/ComplianceBot with a fully mocked Firestore client.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from core.security.audit.compliance_bot import (
    ComplianceBot,
    ComplianceReport,
    ComplianceViolation,
    ConsentManager,
    ConsentRecord,
    ConsentType,
    DataRetentionPolicy,
    DigitalSecurityActChecker,
    GDPRChecker,
    RegulationType,
    compliance_bot,
)


# ---------------------------------------------------------------------------
# Firestore mocking helpers
# ---------------------------------------------------------------------------
def make_db():
    """Return (db_mock, doc_refs) where doc_refs records created doc refs."""
    db = MagicMock()
    return db


def patch_firestore(monkeypatch, db):
    monkeypatch.setattr(
        "core.security.audit.compliance_bot.get_firestore_client",
        lambda: db,
    )


def consent_doc_payload(**overrides):
    now = datetime.now(UTC)
    payload = {
        "user_id": "u1",
        "consent_type": "data_processing",
        "granted": True,
        "granted_at": (now - timedelta(days=1)).isoformat(),
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "version": "1.0",
    }
    payload.update(overrides)
    return payload


def doc_mock(exists=True, data=None):
    d = MagicMock()
    d.exists = exists
    d.to_dict.return_value = data or {}
    return d


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
class TestConsentRecord:
    def test_to_dict_round_trip(self):
        now = datetime.now(UTC)
        rec = ConsentRecord(
            user_id="u1",
            consent_type=ConsentType.ANALYTICS,
            granted=True,
            granted_at=now,
            expires_at=now + timedelta(days=7),
            ip_address="1.2.3.4",
            user_agent="pytest",
            version="2.1",
        )
        d = rec.to_dict()
        assert d["consent_type"] == "analytics"
        assert d["expires_at"] == (now + timedelta(days=7)).isoformat()
        assert d["ip_address"] == "1.2.3.4"
        assert d["version"] == "2.1"
        assert d["withdrawn_at"] is None

    def test_to_dict_none_expiry_and_withdrawn(self):
        now = datetime.now(UTC)
        wd = datetime.now(UTC)
        rec = ConsentRecord(
            user_id="u2",
            consent_type=ConsentType.MARKETING,
            granted=False,
            granted_at=now,
            withdrawn_at=wd,
        )
        d = rec.to_dict()
        assert d["expires_at"] is None
        assert d["withdrawn_at"] == wd.isoformat()

    def test_is_valid_paths(self):
        now = datetime.now(UTC)
        valid = ConsentRecord("u", ConsentType.ANALYTICS, True, now)
        assert valid.is_valid() is True

        not_granted = ConsentRecord("u", ConsentType.ANALYTICS, False, now)
        assert not_granted.is_valid() is False

        withdrawn = ConsentRecord("u", ConsentType.ANALYTICS, True, now, withdrawn_at=now)
        assert withdrawn.is_valid() is False

        expired = ConsentRecord(
            "u",
            ConsentType.ANALYTICS,
            True,
            now - timedelta(days=2),
            expires_at=now - timedelta(days=1),
        )
        assert expired.is_valid() is False

        future_expiry = ConsentRecord(
            "u",
            ConsentType.ANALYTICS,
            True,
            now,
            expires_at=now + timedelta(days=1),
        )
        assert future_expiry.is_valid() is True


class TestViolationAndReport:
    def test_violation_to_dict(self):
        v = ComplianceViolation(
            regulation=RegulationType.GDPR,
            severity="high",
            category="cat",
            description="desc",
            affected_data=["a"],
            remediation="fix",
        )
        d = v.to_dict()
        assert d["regulation"] == "gdpr"
        assert d["severity"] == "high"
        assert d["affected_data"] == ["a"]
        assert "detected_at" in d

    def test_report_to_dict(self):
        v = ComplianceViolation(
            regulation=RegulationType.PCI_DSS,
            severity="low",
            category="c",
            description="d",
        )
        report = ComplianceReport(
            overall_compliant=False,
            regulations_checked=[RegulationType.GDPR, RegulationType.PCI_DSS],
            violations=[v],
            consent_status={"analytics": True},
            data_retention_status={"analytics_limit_days": 365},
            recommendations=["r1"],
        )
        d = report.to_dict()
        assert d["overall_compliant"] is False
        assert d["violations_count"] == 1
        assert d["regulations_checked"] == ["gdpr", "pci_dss"]
        assert d["consent_status"] == {"analytics": True}
        assert d["recommendations"] == ["r1"]


# ---------------------------------------------------------------------------
# GDPRChecker
# ---------------------------------------------------------------------------
class TestGDPRChecker:
    def _checker(self, monkeypatch, db=None):
        db = db or make_db()
        patch_firestore(monkeypatch, db)
        return GDPRChecker(), db

    def test_check_lawful_basis_no_consent(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc_mock(exists=False)
        v = checker.check_lawful_basis("u1", "analytics")
        assert v is not None
        assert v.severity == "critical"
        assert v.category == "lawful_basis"
        assert "analytics" in v.description

    def test_check_lawful_basis_valid_consent(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc_mock(exists=True, data=consent_doc_payload())
        assert checker.check_lawful_basis("u1", "analytics") is None

    def test_check_lawful_basis_invalid_consent(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        # withdrawn consent -> is_valid() False -> violation
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc_mock(exists=True, data=consent_doc_payload(granted=False))
        assert checker.check_lawful_basis("u1", "analytics") is not None

    def test_check_lawful_basis_db_error(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.side_effect = RuntimeError("boom")
        v = checker.check_lawful_basis("u1", "p")
        assert v is not None  # error -> None consent -> violation

    def test_check_data_minimization_excessive(self, monkeypatch):
        checker, _ = self._checker(monkeypatch)
        v = checker.check_data_minimization(
            ["email", "password_hash", "ssn", "salary"], "authentication"
        )
        assert v is not None
        assert v.category == "data_minimization"
        assert set(v.affected_data) == {"ssn", "salary"}

    def test_check_data_minimization_ok(self, monkeypatch):
        checker, _ = self._checker(monkeypatch)
        assert checker.check_data_minimization(["email", "password_hash"], "authentication") is None

    def test_check_data_minimization_unknown_purpose_all_excessive(self, monkeypatch):
        checker, _ = self._checker(monkeypatch)
        v = checker.check_data_minimization(["a", "b"], "unknown_purpose")
        assert v.affected_data == ["a", "b"]

    @pytest.mark.parametrize(
        "data_type,limit",
        [("session_logs", 30), ("analytics", 365), ("chat_history", 90), ("mystery", 365)],
    )
    def test_check_retention_limit(self, monkeypatch, data_type, limit):
        checker, _ = self._checker(monkeypatch)
        assert checker.check_retention_limit(limit - 1, data_type) is None
        v = checker.check_retention_limit(limit + 1, data_type)
        assert v is not None
        assert v.category == "retention_limit"
        assert v.severity == "high"

    def test_check_right_to_deletion_pending(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        where_chain = db.collection.return_value.where.return_value.where.return_value
        where_chain.stream.return_value = [doc_mock(data={"user_id": "u1"})]
        v = checker.check_right_to_deletion("u1")
        assert v is not None
        assert v.category == "right_to_deletion"
        assert v.severity == "critical"

    def test_check_right_to_deletion_none(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        where_chain = db.collection.return_value.where.return_value.where.return_value
        where_chain.stream.return_value = []
        assert checker.check_right_to_deletion("u1") is None

    def test_check_right_to_deletion_db_error(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        where_chain = db.collection.return_value.where.return_value.where.return_value
        where_chain.stream.side_effect = RuntimeError("down")
        assert checker.check_right_to_deletion("u1") is None

    def test_get_consent_success_and_expiry_none(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc_mock(exists=True, data=consent_doc_payload(expires_at=None))
        rec = checker._get_consent("u1", ConsentType.DATA_PROCESSING)
        assert rec is not None
        assert rec.expires_at is None
        assert rec.consent_type == ConsentType.DATA_PROCESSING

    def test_get_consent_missing(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        db.collection.return_value.document.return_value.get.return_value = doc_mock(exists=False)
        assert checker._get_consent("u1", ConsentType.ANALYTICS) is None


# ---------------------------------------------------------------------------
# DigitalSecurityActChecker
# ---------------------------------------------------------------------------
class TestDigitalSecurityActChecker:
    def _checker(self, monkeypatch, db=None):
        db = db or make_db()
        patch_firestore(monkeypatch, db)
        return DigitalSecurityActChecker(), db

    @pytest.mark.parametrize("loc", ["us-east", "eu-west", "singapore"])
    def test_check_data_localization_violation(self, monkeypatch, loc):
        checker, _ = self._checker(monkeypatch)
        v = checker.check_data_localization(loc)
        assert v is not None
        assert v.category == "data_localization"
        assert v.severity == "critical"
        assert set(v.affected_data) == {"nid", "biometric", "financial"}

    @pytest.mark.parametrize("loc", ["bd", "bangladesh"])
    def test_check_data_localization_ok(self, monkeypatch, loc):
        checker, _ = self._checker(monkeypatch)
        assert checker.check_data_localization(loc) is None

    @pytest.mark.parametrize(
        "content",
        [
            "this is a defamatory statement about someone",
            "post hurting religious sentiment of people",
            "plan for cyber terrorism attacks",
            "tutorial on hacking government portals",
        ],
    )
    def test_check_content_moderation_violation(self, monkeypatch, content):
        checker, _ = self._checker(monkeypatch)
        v = checker.check_content_moderation(content)
        assert v is not None
        assert v.category == "content_moderation"
        assert "Section 25" in v.description

    def test_check_content_moderation_clean(self, monkeypatch):
        checker, _ = self._checker(monkeypatch)
        assert checker.check_content_moderation("hello world, all good") is None

    def test_check_lawful_interception_no_audit_logs(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        db.collection.return_value.limit.return_value.stream.return_value = []
        v = checker.check_lawful_interception_readiness()
        assert v is not None
        assert v.category == "lawful_interception"

    def test_check_lawful_interception_ok(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        db.collection.return_value.limit.return_value.stream.return_value = [doc_mock()]
        assert checker.check_lawful_interception_readiness() is None

    def test_check_cybersecurity_reporting_no_plan(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        db.collection.return_value.document.return_value.get.return_value = doc_mock(exists=False)
        v = checker.check_cybersecurity_reporting()
        assert v is not None
        assert v.category == "incident_reporting"
        assert "CIRT" in v.remediation

    def test_check_cybersecurity_reporting_ok(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        db.collection.return_value.document.return_value.get.return_value = doc_mock(exists=True)
        assert checker.check_cybersecurity_reporting() is None

    def test_audit_infrastructure_db_error(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        db.collection.return_value.limit.return_value.stream.side_effect = RuntimeError("x")
        assert checker._check_audit_infrastructure() is False

    def test_incident_plan_db_error(self, monkeypatch):
        checker, db = self._checker(monkeypatch)
        db.collection.return_value.document.return_value.get.side_effect = RuntimeError("x")
        assert checker._check_incident_response_plan() is False


# ---------------------------------------------------------------------------
# ConsentManager
# ---------------------------------------------------------------------------
class TestConsentManager:
    def _mgr(self, monkeypatch, db=None):
        db = db or make_db()
        patch_firestore(monkeypatch, db)
        return ConsentManager(), db

    def test_record_consent_without_expiry(self, monkeypatch):
        mgr, db = self._mgr(monkeypatch)
        rec = mgr.record_consent("u1", ConsentType.MARKETING, True)
        assert rec.granted is True
        assert rec.expires_at is None
        db.collection.return_value.document.return_value.set.assert_called_once()
        stored = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert stored["consent_type"] == "marketing"

    def test_record_consent_with_expiry_and_meta(self, monkeypatch):
        mgr, _ = self._mgr(monkeypatch)
        rec = mgr.record_consent(
            "u1",
            ConsentType.ANALYTICS,
            True,
            ip_address="9.9.9.9",
            user_agent="ua",
            expires_days=30,
        )
        assert rec.expires_at is not None
        assert rec.ip_address == "9.9.9.9"
        assert rec.user_agent == "ua"
        delta = rec.expires_at - rec.granted_at
        assert 29 <= delta.days <= 30

    def test_withdraw_consent_existing(self, monkeypatch):
        mgr, db = self._mgr(monkeypatch)
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc_mock(exists=True, data=consent_doc_payload())
        rec = mgr.withdraw_consent("u1", ConsentType.DATA_PROCESSING)
        assert rec is not None
        assert rec.granted is False
        assert rec.withdrawn_at is not None
        # set() called with updated data
        updated = doc_ref.set.call_args[0][0]
        assert updated["granted"] is False
        assert "withdrawn_at" in updated

    def test_withdraw_consent_missing(self, monkeypatch):
        mgr, db = self._mgr(monkeypatch)
        db.collection.return_value.document.return_value.get.return_value = doc_mock(exists=False)
        assert mgr.withdraw_consent("u1", ConsentType.ANALYTICS) is None

    def test_withdraw_consent_db_error(self, monkeypatch):
        mgr, db = self._mgr(monkeypatch)
        db.collection.return_value.document.return_value.get.side_effect = RuntimeError("x")
        assert mgr.withdraw_consent("u1", ConsentType.ANALYTICS) is None

    def test_get_consent_status(self, monkeypatch):
        mgr, db = self._mgr(monkeypatch)
        db.collection.return_value.where.return_value.stream.return_value = [
            doc_mock(data={"consent_type": "analytics", "granted": True}),
            doc_mock(data={"consent_type": "marketing", "granted": False}),
            doc_mock(data={"no_type": 1}),  # skipped (no consent_type)
        ]
        status = mgr.get_consent_status("u1")
        assert status == {"analytics": True, "marketing": False}

    def test_get_consent_status_db_error(self, monkeypatch):
        mgr, db = self._mgr(monkeypatch)
        db.collection.return_value.where.return_value.stream.side_effect = RuntimeError("x")
        assert mgr.get_consent_status("u1") == {}


# ---------------------------------------------------------------------------
# DataRetentionPolicy
# ---------------------------------------------------------------------------
class TestRetentionPolicy:
    def test_enforce_retention_deletes(self, monkeypatch):
        db = make_db()
        patch_firestore(monkeypatch, db)
        old_doc = MagicMock()
        stream = db.collection.return_value.where.return_value.stream
        stream.return_value = [old_doc, old_doc, old_doc]
        policy = DataRetentionPolicy()
        assert policy.enforce_retention("session_logs", 30) == 3
        assert old_doc.reference.delete.call_count == 3
        # cutoff filter was applied
        db.collection.return_value.where.assert_called_once()

    def test_enforce_retention_error(self, monkeypatch):
        db = make_db()
        patch_firestore(monkeypatch, db)
        db.collection.return_value.where.return_value.stream.side_effect = RuntimeError("x")
        policy = DataRetentionPolicy()
        assert policy.enforce_retention("chat_history", 90) == 0


# ---------------------------------------------------------------------------
# ComplianceBot orchestrator
# ---------------------------------------------------------------------------
class TestComplianceBotRun:
    def _bot(self, monkeypatch, db=None):
        db = db or make_db()
        patch_firestore(monkeypatch, db)
        return ComplianceBot(), db

    def test_all_violations_path(self, monkeypatch):
        bot, db = self._bot(monkeypatch)
        # no consent doc -> lawful basis violation
        db.collection.return_value.document.return_value.get.return_value = doc_mock(exists=False)
        where_chain = db.collection.return_value.where.return_value.where.return_value
        where_chain.stream.return_value = [doc_mock(data={"status": "pending"})]
        report = bot.run_compliance_check(
            user_id="u1",
            data_fields=["email", "salary"],
            purpose="authentication",
            content="defamatory statement inside",
            data_location="us-east",
        )
        cats = {v.category for v in report.violations}
        assert {
            "lawful_basis",
            "data_minimization",
            "right_to_deletion",
            "data_localization",
            "content_moderation",
            "lawful_interception",
            "incident_reporting",
        } <= cats
        assert report.overall_compliant is False
        # recommendations deduped, non-empty
        assert len(report.recommendations) == len(set(report.recommendations))
        assert report.data_retention_status["session_logs_limit_days"] == 30

    def test_compliant_path(self, monkeypatch):
        bot, db = self._bot(monkeypatch)
        doc_ref = db.collection.return_value.document.return_value
        # consents exist (valid), audit logs exist, incident plan exists
        doc_ref.get.return_value = doc_mock(exists=True, data=consent_doc_payload())
        db.collection.return_value.limit.return_value.stream.return_value = [doc_mock()]
        where_chain = db.collection.return_value.where.return_value.where.return_value
        where_chain.stream.return_value = []  # no pending deletions
        # consent status stream
        db.collection.return_value.where.return_value.stream.return_value = []
        report = bot.run_compliance_check(
            user_id="u1",
            data_fields=["email", "password_hash"],
            purpose="authentication",
            content="clean content",
            data_location="bd",
        )
        assert report.overall_compliant is True
        assert report.violations == []
        assert report.recommendations == [
            "Continue current data practices. Keep monitoring regulations."
        ]

    def test_singleton_exists(self):
        assert compliance_bot is not None
        assert isinstance(compliance_bot, ComplianceBot)
