from pathlib import Path

from repository_metadata_index import build_index


def test_index_is_deterministic_and_excludes_generated_dirs(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    first = build_index(tmp_path)
    second = build_index(tmp_path)
    assert first == second
    assert first["file_count"] == 1
    assert first["files"][0]["path"] == "src/main.py"
