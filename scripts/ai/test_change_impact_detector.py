from pathlib import Path

from change_impact_detector import analyze, is_protected, resolve_local_import


def test_protected_paths_require_review():
    assert is_protected(".github/workflows/ci.yml")
    assert is_protected("infrastructure/main.tf")
    assert not is_protected("frontend/src/app.tsx")


def test_missing_local_import_is_blocking(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("from .missing import value\n", encoding="utf-8")
    report = analyze(tmp_path, ["app.py"])
    assert report["status"] == "blocked"
    assert report["findings"][0]["category"] == "broken_import"


def test_existing_local_import_is_resolved(tmp_path: Path):
    source = tmp_path / "app.py"
    dependency = tmp_path / "helper.py"
    source.write_text("from .helper import value\n", encoding="utf-8")
    dependency.write_text("value = 1\n", encoding="utf-8")
    assert resolve_local_import(source, ".helper", tmp_path) == dependency
    assert analyze(tmp_path, ["app.py"])["findings"] == []


def test_package_change_without_lockfile_requires_review(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    report = analyze(tmp_path, ["package.json"])
    assert report["status"] == "review"
    assert report["risk"] == "medium"
    assert report["risk_score"] == 3
    assert report["findings"][0]["category"] == "lockfile_drift"


def test_multiple_high_risk_findings_become_critical(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("from .missing import value\n", encoding="utf-8")
    report = analyze(tmp_path, ["app.py", ".github/workflows/ci.yml"])
    assert report["status"] == "blocked"
    assert report["risk"] == "critical"
    assert report["risk_score"] >= 10
    assert len(report["risk_reasons"]) == 2
