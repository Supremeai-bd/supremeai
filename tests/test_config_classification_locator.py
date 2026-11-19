"""The shared config-classification locator must resolve or refuse loudly.

Both config guards crashed for months on the pre-flattening path
(`backend/core/config_classification.py`), i.e. the only validators of
`config/service_registry.yaml` silently did nothing. A locator that returns an
empty/absent path would recreate exactly that failure, so the contract under
test is: resolve the real file, or exit non-zero with a message that names both
candidates.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import config_classification_locator as locator


def test_resolves_the_live_source():
    path = locator.config_spec_path()
    assert path.is_file()
    assert path.name == "config_classification.py"
    assert path.parent.name == "core"


def test_repo_root_matches_the_git_root():
    assert (locator.REPO_ROOT / "config" / "service_registry.yaml").is_file()


def test_legacy_layout_still_resolves(tmp_path):
    legacy = tmp_path / "backend" / "core"
    legacy.mkdir(parents=True)
    (legacy / "config_classification.py").write_text("CONFIG_SPECS = ()\n", encoding="utf-8")
    assert locator.config_dir(tmp_path) == legacy


def test_new_layout_wins_over_legacy(tmp_path):
    for rel in ("core", "backend/core"):
        d = tmp_path / rel
        d.mkdir(parents=True)
        (d / "config_classification.py").write_text("CONFIG_SPECS = ()\n", encoding="utf-8")
    assert locator.config_dir(tmp_path) == tmp_path / "core"


def test_missing_source_fails_loudly(tmp_path):
    with pytest.raises(SystemExit) as exc:
        locator.config_dir(tmp_path)
    message = str(exc.value)
    assert "config_classification.py" in message
    assert "refusing to pass" in message


def test_both_config_guards_use_the_shared_locator():
    """A private copy is how the drift started; the clone gate flagged it too."""
    for name in ("validate_config_registry.py", "check_config_contract.py"):
        text = (REPO_ROOT / "scripts" / "ci" / name).read_text(encoding="utf-8")
        assert "config_classification_locator" in text, name
        assert 'def _config_dir()' not in text, name
