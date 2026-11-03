"""ComplianceBot এজেন্টের ইউনিট টেস্ট।

বাংলা: শুধু পিওর লজিক (Enum, ConsentRecord.is_valid, to_dict সিরিয়ালাইজেশন)
কভার করা হয়েছে। Firestore/network নির্ভর মেথড আলাদা ইন্টিগ্রেশন টেস্টের জন্য।
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.security.audit.compliance_bot import (
    ComplianceReport,
    ComplianceViolation,
    ConsentRecord,
    ConsentType,
    RegulationType,
)


def test_regulation_type_values():
    assert RegulationType.GDPR.value == "gdpr"
    assert RegulationType.DIGITAL_SECURITY_ACT_BD.value == "digital_security_act_bd"
    assert RegulationType.PCI_DSS.value == "pci_dss"
    assert RegulationType.HIPAA.value == "hipaa"


def test_consent_type_values():
    assert ConsentType.DATA_PROCESSING.value == "data_processing"
    assert ConsentType.THIRD_PARTY_SHARING.value == "third_party_sharing"


def test_consent_record_valid_when_granted():
    rec = ConsentRecord(
        user_id="u1",
        consent_type=ConsentType.DATA_PROCESSING,
        granted=True,
        granted_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    assert rec.is_valid() is True


def test_consent_record_invalid_when_not_granted():
    rec = ConsentRecord(
        user_id="u1",
        consent_type=ConsentType.MARKETING,
        granted=False,
        granted_at=datetime.now(UTC),
    )
    assert rec.is_valid() is False


def test_consent_record_invalid_when_withdrawn():
    rec = ConsentRecord(
        user_id="u1",
        consent_type=ConsentType.ANALYTICS,
        granted=True,
        granted_at=datetime.now(UTC),
        withdrawn_at=datetime.now(UTC),
    )
    assert rec.is_valid() is False


def test_consent_record_invalid_when_expired():
    rec = ConsentRecord(
        user_id="u1",
        consent_type=ConsentType.LOCATION,
        granted=True,
        granted_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert rec.is_valid() is False


def test_consent_record_to_dict():
    now = datetime.now(UTC)
    rec = ConsentRecord(
        user_id="u1",
        consent_type=ConsentType.DATA_PROCESSING,
        granted=True,
        granted_at=now,
        version="2.1",
    )
    d = rec.to_dict()
    assert d["user_id"] == "u1"
    assert d["consent_type"] == "data_processing"
    assert d["granted"] is True
    assert d["version"] == "2.1"
    assert d["granted_at"] == now.isoformat()


def test_compliance_violation_to_dict():
    v = ComplianceViolation(
        regulation=RegulationType.GDPR,
        severity="high",
        category="data_retention",
        description="Logs retained too long",
        affected_data=["user_logs"],
        remediation="Reduce retention window",
    )
    d = v.to_dict()
    assert d["regulation"] == "gdpr"
    assert d["severity"] == "high"
    assert d["affected_data"] == ["user_logs"]


def test_compliance_report_to_dict():
    report = ComplianceReport(
        overall_compliant=False,
        regulations_checked=[RegulationType.GDPR, RegulationType.PCI_DSS],
        violations=[
            ComplianceViolation(
                regulation=RegulationType.GDPR,
                severity="critical",
                category="consent",
                description="Missing consent",
            )
        ],
        consent_status={"u1": "valid"},
        data_retention_status={"logs": "ok"},
    )
    d = report.to_dict()
    assert d["overall_compliant"] is False
    assert d["regulations_checked"] == ["gdpr", "pci_dss"]
    assert d["violations_count"] == 1
