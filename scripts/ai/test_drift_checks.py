from pathlib import Path

from drift_checks import analyze


def test_missing_deployment_source_is_reported(tmp_path: Path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "Dockerfile").write_text("COPY missing.py /app/missing.py\n", encoding="utf-8")
    report = analyze(tmp_path)
    assert report["status"] == "review"
    assert report["findings"][0]["category"] == "deployment_drift"


def test_clean_repository_has_no_drift(tmp_path: Path):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "Dockerfile").write_text("COPY frontend /app/frontend\n", encoding="utf-8")
    (tmp_path / "frontend").joinpath("package.json").write_text("{}", encoding="utf-8")
    assert analyze(tmp_path)["status"] == "pass"
