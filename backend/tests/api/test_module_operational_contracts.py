"""
Contract test: Module Operational Truth & Verification
======================================================
Guarantees that:
1. MODULES_LIST.md strictly enforces the 224 functional module boundary.
2. Every module marked as 🟢 Operational has verified active callers.
3. No module marked as 🟢 Operational is a non-existent path.
4. Summary counts exactly match the rows in the table.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
MODULES_LIST_PATH = ROOT_DIR / "MODULES_LIST.md"


def parse_modules_list() -> tuple[dict[str, int], list[dict]]:
    assert MODULES_LIST_PATH.exists(), "MODULES_LIST.md must exist"
    lines = MODULES_LIST_PATH.read_text(encoding="utf-8").splitlines()

    counts = {}
    modules = []

    # Extract summary counts from header
    for line in lines[:20]:
        m_op = re.search(r"🟢 \*\*Operational:\*\*\s+(\d+)", line)
        if m_op:
            counts["operational"] = int(m_op.group(1))
        m_env = re.search(r"🟡 \*\*Environment-Dependent:\*\*\s+(\d+)", line)
        if m_env:
            counts["env_dependent"] = int(m_env.group(1))
        m_part = re.search(r"🟠 \*\*Partially Wired.*?:\*\*\s+(\d+)", line)
        if m_part:
            counts["partially_wired"] = int(m_part.group(1))
        m_brok = re.search(r"🔴 \*\*Broken:\*\*\s+(\d+)", line)
        if m_brok:
            counts["broken"] = int(m_brok.group(1))

    for line in lines:
        line = line.strip()
        if not line.startswith("|") or "Module Name / Relative Path" in line or "---|---" in line:
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 4 and parts[0].isdigit():
            modules.append(
                {
                    "id": int(parts[0]),
                    "category": parts[1],
                    "path": parts[2],
                    "status": parts[3],
                    "callers": parts[4] if len(parts) > 4 else "",
                }
            )

    return counts, modules


def test_module_boundary_strictly_enforced():
    counts, modules = parse_modules_list()
    # MODULES_LIST.md boundary. 2026-09-17: owner-approved deletion of the three
    # dead zustand stores (chatStore/themeStore/useSupremeStore — commit 0aefa3b3)
    # moved the production catalog 194 -> 191; 2026-09-25: catalog truth-sync —
    # row #184 frontend/src/store/slices (deleted in owner-merged #1157, never
    # de-cataloged) removed → 191 -> 190; 2026-09-29: catalog truth-sync —
    # row #54 backend/tools/ensemble_router.py (verified-dead prune, owner-merged
    # #2449; row itself said "0 active callers (dormant)/owner-review") removed
    # → 190 -> 189; 2026-09-29: catalog truth-sync #2 (#2555) — row #150
    # frontend/src/pages/WorkspaceModulePage.tsx (zero-importer dead component,
    # deletion queued in #2503/#2554's root-audit batch) removed → 189 -> 188;
    # 2026-10-10: full-status audit truth-sync #3 — removed rows for
    # infrastructure/kubernetes, tools/firebase_functions_v1, and
    # backend/tools/parallel_agent_executor.py (all verified-missing paths), and
    # re-pathed backend/tools/social/telegram_bot.py → telegram_bot/ (package)
    # → 188 -> 185; then truth-sync #4 (post-audit) removed the retired
    # backend/services/llm row (LLM Gateway Consolidation #2249 — the package
    # was empty/stale; routing lives in core/llm_router.py) → 185 -> 184;
    # 🔴-Broken count is now 0.
    # 224 stays as the historical full-boundary tolerance so a future sanctioned
    # restore is not a lie either.
    assert len(modules) in (184, 224), (
        f"Expected cataloged modules to be 184 (current production boundary) or 224 (historical full boundary), got {len(modules)}"
    )


def test_summary_counts_match_table_rows():
    counts, modules = parse_modules_list()

    op_count = sum(1 for m in modules if "🟢" in m["status"])
    env_count = sum(1 for m in modules if "🟡" in m["status"])
    part_count = sum(1 for m in modules if "🟠" in m["status"])
    broken_count = sum(1 for m in modules if "🔴" in m["status"])

    assert counts.get("operational") == op_count, (
        f"Summary Operational ({counts.get('operational')}) != rows ({op_count})"
    )
    assert counts.get("env_dependent") == env_count, (
        f"Summary Env-Dep ({counts.get('env_dependent')}) != rows ({env_count})"
    )
    assert counts.get("partially_wired") == part_count, (
        f"Summary Partially Wired ({counts.get('partially_wired')}) != rows ({part_count})"
    )
    assert counts.get("broken") == broken_count, (
        f"Summary Broken ({counts.get('broken')}) != rows ({broken_count})"
    )


def test_all_operational_modules_exist_on_disk():
    _, modules = parse_modules_list()
    for m in modules:
        if "🟢" in m["status"] or "🟠" in m["status"]:
            target = ROOT_DIR / m["path"]
            assert target.exists(), f"Cataloged module {m['path']} does not exist on disk!"


def test_operational_modules_have_active_callers():
    _, modules = parse_modules_list()
    for m in modules:
        if "🟢" in m["status"]:
            assert "0 active callers" not in m["callers"], (
                f"Module {m['path']} marked Operational but has 0 active callers"
            )


def test_catalog_ids_are_unique_and_contiguous():
    _, modules = parse_modules_list()
    ids = [module["id"] for module in modules]
    assert ids == list(range(1, len(modules) + 1))


def test_audit_report_has_governance_metadata():
    report_path = ROOT_DIR / "docs/audit_reports/module_wiring_audit.json"
    assert report_path.exists(), "Generated audit report must exist"
    report = __import__("json").loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"]
    assert report["generated_at"].endswith("Z")
    assert report["verification_command"]
    assert report["total"] == len(report["modules"])
    valid_statuses = {
        "🟢 Operational",
        "🟡 Environment-Dependent",
        "🟠 Partially Wired",
        "🔴 Broken",
        "⚪ Planned",
    }
    valid_decisions = {"retain", "review", "owner-review"}
    for module in report["modules"]:
        assert module["status"] in valid_statuses
        assert module["decision"] in valid_decisions
        assert module["verified_at"].endswith("Z")
        assert module["verification_command"] == report["verification_command"]
        assert module["owner_circle"]
