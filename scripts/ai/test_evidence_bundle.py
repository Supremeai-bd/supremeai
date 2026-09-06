import json
from pathlib import Path

from evidence_bundle import build_bundle


def test_bundle_links_commit_and_hashes(tmp_path: Path, monkeypatch):
    report = tmp_path / "report.json"
    report.write_text('{"status":"pass"}\n', encoding="utf-8")
    monkeypatch.setattr("evidence_bundle.git_value", lambda *args: "abc123")
    bundle = build_bundle(tmp_path, [report])
    assert bundle["commit"] == "abc123"
    assert bundle["reports"][0]["path"] == str(report)
    assert len(bundle["reports"][0]["sha256"]) == 64
    assert bundle["status"] == "complete"
    assert bundle["missing_reports"] == []


def test_bundle_marks_missing_reports_incomplete(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("evidence_bundle.git_value", lambda *args: "abc123")
    bundle = build_bundle(tmp_path, [tmp_path / "missing.json"])
    assert bundle["status"] == "incomplete"
    assert bundle["reports"] == []
    assert bundle["missing_reports"] == [str(tmp_path / "missing.json")]
