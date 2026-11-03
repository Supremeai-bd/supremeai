"""Tests for dependency_parasite_guard (Guardian gate)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.dependency_parasite_guard import (
    audit_dependencies,
    audit_requirements_text,
    audit_package_json_text,
    parse_requirements,
    parse_package_json,
)


def test_parse_requirements() -> None:
    deps = parse_requirements("requests==2.31.0\n# comment\nflask>=2.0\n")
    assert len(deps) == 2
    assert deps[0]["name"] == "requests"


def test_unpinned_flagged() -> None:
    errs = audit_requirements_text("requests\n")
    assert any("unpinned" in e for e in errs)


def test_duplicate_flagged() -> None:
    errs = audit_requirements_text("requests==1.0\nrequests==2.0\n")
    assert any("duplicate" in e for e in errs)


def test_parasite_package_flagged() -> None:
    errs = audit_package_json_text(json.dumps({"dependencies": {"event-stream": "3.3.6"}}))
    assert any("parasitic" in e for e in errs)


def test_clean_passes() -> None:
    assert audit_requirements_text("requests==2.31.0\nflask>=2.0\n") == []
    assert audit_package_json_text(json.dumps({"dependencies": {"lodash": "^4.0.0"}})) == []


def test_scan_paths_via_main_not_needed(tmp_path: Path) -> None:
    # exercise audit_dependencies directly
    deps = [{"name": "a", "spec": ""}, {"name": "a", "spec": "1.0"}]
    errs = audit_dependencies(deps)
    assert len(errs) >= 2