import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ops"))

import ast_graph_index as agi  # noqa: E402


def test_parse_function():
    rec = agi.parse_file(ROOT / "scripts" / "ci" / "pr_preflight_guard.py")
    names = [f["name"] for f in rec["functions"]]
    assert "check_branch" in names


def test_build_graph():
    g = agi.build_graph(ROOT, limit=3)
    assert g["file_count"] == 3
    assert "files" in g


def test_self_test():
    assert agi.self_test() == 0
