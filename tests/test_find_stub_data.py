"""ERR-M01 regression tests — find_stub_data.py detects comment-based stubs.

বাংলা: স্ক্যানার আগে কমেন্ট লাইন blanket-skip করত, ফলে কমেন্ট-ভিত্তিক স্টাব
মার্কার (`# Task execution logic would go here` — kaggle_orchestrator) কখনোই
ধরা পড়ত না — `stub_marker_comment` প্যাটার্নটি ছিল dead। এখন
COMMENT_AWARE_PATTERNS কমেন্ট লাইনেও স্ক্যান হয়, আর কোড-প্যাটার্ন আগের মতোই
false-positive এড়াতে কমেন্ট স্কিপ করে।
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from find_stub_data import (  # noqa: E402
    COMMENT_AWARE_PATTERNS,
    is_excepted,
    scan_directory,
    scan_file,
)


def _scan_tmp(_tmp_path=None, name: str = "sample.py", content: str = "") -> list[dict]:
    """Scan a file in a plain temp dir.

    বাংলা: pytest-এর tmp_path ডিরেক্টরি নাম `test_*` দিয়ে শুরু হয় — স্ক্যানারের
    `test_*.py` exception glob fnmatch-এ `*` ডিরেক্টরি বাউন্ডারি ক্রস করে বলে
    সেটা false-except হয়। তাই নিরপেক্ষ tempfile.mkdtemp ব্যবহার করা হচ্ছে।
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / name
        target.write_text(content, encoding="utf-8")
        return scan_file(str(target))


class TestCommentAwarePatterns:
    def test_template_stub_comment_detected(self, tmp_path):
        """The exact Kaggle-style stub from the register audit is now caught."""
        findings = _scan_tmp(
            name="kernel.py",
            content="def _generate_kernel_code():\n"
            "    # Task execution logic would go here\n"
            "    pass\n",
        )
        assert any(f["pattern"] == "stub_marker_comment" for f in findings)

    def test_not_implemented_comment_detected(self, tmp_path):
        findings = _scan_tmp(
            name="svc.py", content="def handle():\n    # not implemented yet\n    raise RuntimeError\n"
        )
        assert any(f["pattern"] == "stub_marker_comment" for f in findings)

    def test_todo_replace_mock_comment_detected(self, tmp_path):
        findings = _scan_tmp(
            name="api.py", content="def call():\n    # TODO: replace this mock with the real client\n    return None\n"
        )
        assert any(f["pattern"] == "todo_replace_mock" for f in findings)

    def test_code_patterns_still_skip_comments(self, tmp_path):
        """No false positive: a code-pattern regex must not fire on a comment."""
        findings = _scan_tmp(
            name="const.py",
            content="# MOCK_DATA_CONSTANT: this comment mentions MOCK_DATA\nX = 1\n",
        )
        assert findings == []

    def test_code_pattern_on_code_line_still_works(self, tmp_path):
        findings = _scan_tmp(
            name="cfg.py", content='MOCK_DATA = ["a", "b"]\n'
        )
        assert any(f["pattern"] == "mock_data_constant_py" for f in findings)


class TestExceptionsAndExclusion:
    def test_tests_directory_excepted_for_comment_markers(self):
        assert is_excepted("backend/tests/api/test_x.py", "stub_marker_comment")
        assert not is_excepted("backend/adaptive_engine/mcp_skeleton.py", "stub_marker_comment")

    def test_scan_directory_excludes_dirs(self, tmp_path):
        # বাংলা: pytest tmp_path নাম `test_*` হয় — glob false-except এড়াতে নিরপেক্ষ ডির।
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".venv").mkdir()
            (root / ".venv" / "hidden.py").write_text(
                "# would go here\n", encoding="utf-8"
            )
            (root / "app.py").write_text("# would go here\n", encoding="utf-8")
            findings = scan_directory(str(root), exclude_dirs=[".venv"])
            assert all("hidden" not in f["file"] for f in findings)
            assert any(f["pattern"] == "stub_marker_comment" for f in findings)


def test_comment_aware_set_membership():
    """Guard: the three comment-marker patterns stay comment-aware."""
    assert {
        "stub_marker_comment",
        "todo_replace_mock",
        "simulate_saving_comment",
    } == COMMENT_AWARE_PATTERNS
