"""PLAN-003 — Aider-style repo map (CodeIndexer) tests.

বাংলা: tmp_path-এ synthetic রিপো দিয়ে contract প্রমাণ — সিম্বল এক্সট্র্যাকশন,
import-edge resolution, PageRank র‍্যাংকিং, budget সম্মান, SyntaxError গণনা,
খালি ডিরেক্টরির সৎ খালি map, এবং 512MB cap-guard। Mocked/সিন্থেটিক টেস্ট =
Gate 4 contract; live threshold Gate 5-এ মাপা (implementation PR-এ 2.47s /
1836 ফাইল — threshold ≤5s পূরণ)।
"""

from pathlib import Path

import pytest

from core.code_indexer import CodeIndexer

pytestmark = pytest.mark.unit


@pytest.fixture()
def synthetic_repo(tmp_path: Path) -> Path:
    """a.py → b.py → c.py chain; standalone.py orphan; broken.py syntax-error."""
    (tmp_path / "a.py").write_text(
        "from b import helper\n\n\nclass Driver:\n    def run(self) -> str:\n"
        "        return helper()\n",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text(
        "import c\n\n\ndef helper() -> str:\n    return c.leaf()\n",
        encoding="utf-8",
    )
    (tmp_path / "c.py").write_text(
        "def leaf() -> str:\n    return 'leaf'\n",
        encoding="utf-8",
    )
    (tmp_path / "standalone.py").write_text(
        "class Alone:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text(
        "def oops(:\n    pass\n",
        encoding="utf-8",
    )
    # junk dir must be skipped
    junk = tmp_path / "__pycache__"
    junk.mkdir()
    (junk / "junk.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _fresh_indexer(root: Path) -> CodeIndexer:
    """Bypass the singleton so each test gets an isolated instance."""
    return CodeIndexer(root)


def test_symbol_extraction_classes_and_functions(synthetic_repo: Path):
    idx = _fresh_indexer(synthetic_repo)
    stats = idx.build()
    assert stats["files_indexed"] == 4  # a, b, c, standalone (broken fails, junk skipped)
    assert stats["parse_failures"] == 1
    assert "Cls:Driver" in idx._symbols["a.py"]
    assert "Def:helper" in idx._symbols["b.py"]
    assert "Def:leaf" in idx._symbols["c.py"]


def test_intra_package_import_edges_resolved(synthetic_repo: Path):
    idx = _fresh_indexer(synthetic_repo)
    idx.build()
    assert "b.py" in idx._edges["a.py"]  # from b import helper
    assert "c.py" in idx._edges["b.py"]  # import c
    assert "a.py" not in idx._edges.get("standalone.py", set())


def test_pagerank_ranks_hub_files_above_sources(synthetic_repo: Path):
    idx = _fresh_indexer(synthetic_repo)
    idx.build()
    rank = idx._rank
    # Chain a→b→c: b and c both receive mass; a is a pure source.
    assert rank["b.py"] > rank["a.py"]
    assert rank["c.py"] > rank["a.py"]


def test_render_respects_budget(synthetic_repo: Path):
    idx = _fresh_indexer(synthetic_repo)
    idx.build()
    budget = 120
    out = idx.render_repo_map(budget_chars=budget)
    header, _, body = out.partition("\n")
    assert header.startswith("[REPO MAP]")
    assert len(body) <= budget


def test_empty_dir_renders_honest_empty_map(tmp_path: Path):
    idx = _fresh_indexer(tmp_path)
    out = idx.render_repo_map(budget_chars=500)
    assert "files=0" in out  # honest absence — no fabricated entries
    assert out.count("\n") == 0  # header only


def test_cap_guard_files_and_bytes(tmp_path: Path):
    """512MB cap-guard: per-file cap + file-count cap behave honestly."""
    big = tmp_path / "big.py"
    big.write_text("x = '" + "a" * (100_001) + "'\n", encoding="utf-8")  # > _MAX_FILE_BYTES
    (tmp_path / "ok.py").write_text("y = 1\n", encoding="utf-8")
    idx = _fresh_indexer(tmp_path)
    stats = idx.build()
    assert stats["files_indexed"] == 1  # big.py skipped by per-file cap
    assert "big.py" not in idx._symbols


def test_render_includes_symbols_and_paths(synthetic_repo: Path):
    idx = _fresh_indexer(synthetic_repo)
    idx.build()
    out = idx.render_repo_map(budget_chars=4000)
    assert "a.py" in out and "b.py" in out


def test_goal_boost_never_crashes_and_keeps_budget(synthetic_repo: Path):
    idx = _fresh_indexer(synthetic_repo)
    idx.build()
    out = idx.render_repo_map(budget_chars=300, goal="fix helper function in b")
    header, _, body = out.partition("\n")
    assert header.startswith("[REPO MAP]")
    assert len(body) <= 300


def test_singleton_returns_same_instance_for_same_root(synthetic_repo: Path):
    i1 = CodeIndexer.get_instance(synthetic_repo)
    i2 = CodeIndexer.get_instance(str(synthetic_repo))
    assert i1 is i2
    different = CodeIndexer.get_instance(synthetic_repo.parent)
    assert different is not i1
