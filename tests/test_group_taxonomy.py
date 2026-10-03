# বাংলা মন্তব্য: #3088 §2 — canonical group taxonomy + group-first discovery টেস্ট।
"""group_taxonomy.py — taxonomy validation, label-parsing, group-first lookup (FakeGh)।"""
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "agents"))

from group_taxonomy import (  # noqa: E402
    PRIMARY_GROUPS,
    group_first_lookup,
    normalize_group,
    primary_group_of_labels,
    validate_primary_group,
)


# ── taxonomy validation (#3088 §2) ───────────────────────────────────────────

def test_eight_canonical_groups():
    assert PRIMARY_GROUPS == (
        "governance", "security", "pipeline", "architecture",
        "reliability", "product", "intelligence", "infrastructure",
    )


def test_normalize_group_case_insensitive_and_label_stripping():
    assert normalize_group("GOVERNANCE") == "governance"
    assert normalize_group("group:Pipeline") == "pipeline"
    assert normalize_group("  Security ") == "security"


def test_validate_canonical_group():
    v = validate_primary_group("GOVERNANCE")
    assert v.is_canonical and v.known and v.group == "governance"


def test_validate_legacy_group_advisory_not_blocked():
    # বাংলা মন্তব্য: legacy group (pipeline-failures) advisory — চালু ফ্লো ভাঙা নিষিদ্ধ।
    v = validate_primary_group("pipeline-failures")
    assert v.is_legacy and v.known and not v.is_canonical
    assert v.advisory_only


def test_validate_unknown_group_is_advisory_not_hard_block():
    v = validate_primary_group("some-brand-new-group")
    assert not v.known and not v.is_canonical
    assert v.advisory_only  # rollout: observe-only → blocking পরের slice


def test_primary_group_of_labels():
    assert primary_group_of_labels(["group:pipeline", "P1-high"]) == "pipeline"
    assert primary_group_of_labels(["P1-high", "type:bug"]) is None
    # একাধিক group থাকলে deterministic (lexicographic first)
    assert primary_group_of_labels(["group:zzz", "group:aaa"]) == "aaa"


# ── group-first lookup (#3088 §3 — FakeGh monkeypatch) ──────────────────────

class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def test_group_first_lookup_reports_states(monkeypatch):
    payload = json.dumps([
        {"number": 101, "title": "a", "labels": [{"name": "group:pipeline"}, {"name": "status:in-progress"}]},
        {"number": 102, "title": "b", "labels": [{"name": "group:pipeline"}, {"name": "has-pr"}]},
        {"number": 103, "title": "c", "labels": [{"name": "group:pipeline"}]},
        {"number": 104, "title": "d", "labels": [{"name": "group:pipeline"}, {"name": "type:ledger"}]},
    ])
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted(payload))
    report = group_first_lookup("pipeline")
    assert report.lookup_ok and report.active_count == 4
    states = report.issues_by_state()
    assert states["in_progress"] == [101]
    assert states["has_pr"] == [102]
    assert states["claimable"] == [103]
    assert states["other"] == [104]


def test_group_first_lookup_fail_open_on_gh_failure(monkeypatch):
    # বাংলা মন্তব্য: API-down → lookup_ok=False, exception নয় — caller advisory চালাবে।
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted("", returncode=1))
    report = group_first_lookup("security")
    assert not report.lookup_ok
    assert report.active_issues == []
    assert report.error


def test_group_first_lookup_empty_group(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted("[]"))
    report = group_first_lookup("product")
    assert report.lookup_ok and report.active_count == 0
