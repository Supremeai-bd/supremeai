"""Clone-report parsing for the duplicate regression gate.

The gate fails a PR when it adds genuinely NEW clones, so the parser is the
load-bearing part: a path that is not normalised to repo-relative form, or a
change that only touches already-known clones, must not be reported as new.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import detect_new_duplicates as dupes  # noqa: E402


def test_paths_are_normalised_to_repo_relative_forward_slashes():
    assert dupes._norm(".\\core\\main.py") == "core/main.py"
    assert dupes._norm("././gateway/main.py") == "gateway/main.py"
    assert dupes._norm("gateway/main.py") == "gateway/main.py"


def test_clone_from_json_reads_both_locations():
    clone = dupes.clone_from_json(
        {
            "format": "python",
            "lines": 12,
            "tokens": 80,
            "firstFile": {"name": "./a/one.py", "start": 1, "end": 12},
            "secondFile": {"name": "b\\two.py", "start": 4, "end": 15},
        },
        kind="duplication",
    )
    assert clone.file_a == "a/one.py"
    assert clone.file_b == "b/two.py"
    assert (clone.start_a, clone.end_a) == (1, 12)
    assert clone.kind == "duplication"
    assert clone.lines == 12


def test_missing_optional_fields_degrade_to_zero_not_crash():
    clone = dupes.clone_from_json(
        {"firstFile": {"name": "x.py"}, "secondFile": {"name": "y.py"}},
        kind="duplication",
    )
    assert clone.lines == 0 and clone.tokens == 0
    assert clone.format == "unknown"
