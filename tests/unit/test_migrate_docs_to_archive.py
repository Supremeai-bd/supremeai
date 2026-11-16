"""Regression test for scripts.ops.migrate_docs_to_archive.

Ensures:
1. Constitutional SSOT files, .agents/, and skills/ are strictly MUST-KEEP.
2. Identical source and destination repositories trigger a fatal safety abort.
3. Only verified historical documents are marked archivable.
"""

from __future__ import annotations

import pathlib
from scripts.ops.migrate_docs_to_archive import (
    is_must_keep,
    collect_archivable_files,
    migrate,
    MUST_KEEP_FILES,
    ARCHIVE_REPO,
)


def test_constitutional_files_must_keep():
    critical_files = [
        "README.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "docs/PR_TO_PRODUCTION_LIFECYCLE.md",
        "docs/CONSUMERS.md",
        "docs/AGENT_LOOP_SPEC.md",
        "docs/AUTONOMY_LOOP_CONTRACT.md",
        "docs/LOOP_ALIGNMENT.md",
        "docs/SECURITY.md",
        "docs/INDEX.md",
        "docs/SCOUT_RADAR_INDEX.md",
        ".agents/skills/fastapi-pro/SKILL.md",
        ".agents/rules/AGENT_OPERATING_CONTRACT.md",
        "skills/installer.py",
        "skills/agent-cadence-dispatcher/SKILL.md",
    ]
    for rel_path in critical_files:
        assert is_must_keep(rel_path) is True, f"Expected {rel_path} to be marked MUST KEEP"


def test_explicit_archivable_files_are_not_kept():
    archivable = [
        "docs/FRONTEND_PERFECTION_PLAN.md",
        "docs/SOCIAL_MEDIA_AUTOMATION_PLAN.md",
        "docs/SUPREMEAI_DESKTOP_ANDROID_PLAN.md",
        "docs/ARCHITECTURAL_COMPARISON_AND_ADOPTION_BLUEPRINT.md",
        "docs/architecture/REMAINING_PHASES_IMPL_PLAN.md",
        "docs/architecture/FEATURE_PARITY_RETIREMENT_QUEUE.md",
    ]
    for rel_path in archivable:
        assert is_must_keep(rel_path) is False, f"Expected {rel_path} to be archivable"


def test_safety_check_against_identical_dest(tmp_path, monkeypatch):
    test_repo = tmp_path / "test_repo"
    test_repo.mkdir()
    docs = test_repo / "docs"
    docs.mkdir()
    (docs / "FRONTEND_PERFECTION_PLAN.md").write_text("# Old plan", encoding="utf-8")

    monkeypatch.setattr("scripts.ops.migrate_docs_to_archive.FEDERATION_ROOT", tmp_path)
    monkeypatch.setattr("scripts.ops.migrate_docs_to_archive.ARCHIVE_REPO", test_repo)
    monkeypatch.setattr("scripts.ops.migrate_docs_to_archive.ACTIVE_REPOS", ["test_repo"])

    exit_code = migrate(dry_run=False)
    assert exit_code == 1, "Expected fatal error exit code 1 when ARCHIVE_REPO == repo_dir"
    assert (docs / "FRONTEND_PERFECTION_PLAN.md").exists(), "Source file must not be deleted on abort"
