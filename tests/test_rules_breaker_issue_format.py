"""Tests for rules_breaker issue-format (#3278) — template-compliant findings.

#2912 chain-doctrine: API-created issue-ও fixed template মানতে হবে — নাহলে
Template Guard `template:violating` দেয় → claim/branch/PR সব ব্লক। এই টেস্টগুলো
গার্ড করে যে rules_breaker-এর তৈরি issue প্রথমবারেই compliant।
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.agents.rules_breaker import (
    _FINDING_LABELS_BASE,
    build_finding_issue,
)

# template_gate.py-এর DEFAULT issue-policy (SSOT-এর সাথে sync — চুক্তি-টেস্ট)
TITLE_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test|perf|audit|ops|task)\([^)]+\): .+")
REQUIRED_SECTIONS = ["Mission", "Touching Files", "Verification"]


def _sample_finding(severity: str = "BLOCK") -> dict:
    return {
        "file": "backend/services/auth.py",
        "line": 42,
        "snippet": 'API_KEY = "sk-abcdefghij1234567890"',
        "rule": "sec.hardcoded_secret",
        "severity": severity,
        "description": "[Hardcoded Secret] API key hardcoded in source",
    }


class TestBuildFindingIssue:
    def test_title_convention(self):
        title, _, _ = build_finding_issue(_sample_finding(), "secret-hardcoding", "glm5.2-coder-1")
        assert TITLE_RE.match(title), f"title-convention violated: {title}"
        assert "auth.py:42" in title

    def test_required_sections_present(self):
        _, body, _ = build_finding_issue(_sample_finding(), "secret-hardcoding", "glm5.2-coder-1")
        for section in REQUIRED_SECTIONS:
            assert section in body, f"missing template section: {section}"
        # Priority-section আলাদাভাবে (template_gate-এর মতো করে)
        assert "Priority Tier" in body

    def test_finding_fields_in_body(self):
        f = _sample_finding()
        _, body, _ = build_finding_issue(f, "secret-hardcoding", "agent-x")
        for value in (f["file"], str(f["line"]), f["rule"], f["snippet"]):
            assert value in body, f"finding field missing from body: {value}"

    @pytest.mark.parametrize("severity,priority", [
        ("BLOCK", "P1-high"),
        ("WARN", "P2-medium"),
        ("INFO", "P3-low"),
        ("UNKNOWN_SEV", "P2-medium"),
    ])
    def test_severity_to_priority_mapping(self, severity, priority):
        f = _sample_finding(severity=severity)
        _title, body, labels = build_finding_issue(f, "scan", "agent-x")
        assert priority in labels
        assert priority in body

    def test_labels_canonical_and_no_legacy(self):
        _, _, labels = build_finding_issue(_sample_finding(), "scan", "agent-x")
        # পুরনো মৃত-লেবেল আর নেই
        for dead in ("vulnerability", "rules-breaker"):
            assert dead not in labels
        assert not any(lbl.startswith("severity:") for lbl in labels)
        # canonical বেস + priority
        for lbl in _FINDING_LABELS_BASE:
            assert lbl in labels

    def test_labels_exist_in_repo_taxonomy(self):
        # এই লেবেল-সেট রিপোর বাস্তব লেবেল-তালিকায় বিদ্যমান (auto-create ছাড়াই চলবে)
        _, _, labels = build_finding_issue(_sample_finding(), "scan", "agent-x")
        expected_repo_labels = {
            "type:security", "area:security", "handoff:coder",
            "status:unclaimed", "P1-high", "P2-medium", "P3-low",
        }
        for lbl in labels:
            assert lbl in expected_repo_labels, f"label not in repo taxonomy: {lbl}"

    def test_touching_files_section_contains_finding_file(self):
        f = _sample_finding()
        _, body, _ = build_finding_issue(f, "scan", "agent-x")
        # Touching Files সেকশনে ফাইন্ডিং-ফাইল — Scope Gate-এর ভিত্তি
        section = body.split("### Touching Files")[1].split("###")[0]
        assert f["file"] in section

    def test_verification_contract_three_tier(self):
        _, body, _ = build_finding_issue(_sample_finding(), "scan", "agent-x")
        section = body.split("3-Tier Verification Contract")[1]
        for tier in ("Reflection", "Syntax/Boot", "Tests"):
            assert tier in section


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
