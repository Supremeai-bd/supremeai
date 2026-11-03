"""Unit tests for per-group coverage cache keys (issue #471).

বাংলা: #471-এর cache key চুক্তি লক করে — identical input → identical key,
যেকোনো behavioral input (measured source / pyproject / lock / root conftest /
group scope) বদলালে key বদলাবেই। Key ভুল হলে scoped mode-এর সৎ numerator
ভাঙবে (PR #343 চুক্তি), তাই এগুলো gate-protection টেস্ট।

All cases build hermetic tmp trees — the real backend tree is hashed only
by the ci.yml --cov equivalence lock (read-only).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CKEY_PATH = REPO_ROOT / "scripts" / "ci" / "coverage_cache_keys.py"

_spec = importlib.util.spec_from_file_location("coverage_cache_keys", CKEY_PATH)
ckey = importlib.util.module_from_spec(_spec)
sys.modules["coverage_cache_keys"] = ckey
_spec.loader.exec_module(ckey)


def build_fake_backend(tmp_path: Path) -> Path:
    """Materialize a minimal but representative backend tree."""
    backend = tmp_path / "backend"
    for pkg in ("core", "api", "services", "tools", "runs", "memory"):
        (backend / pkg).mkdir(parents=True)
        (backend / pkg / "mod.py").write_text(f"# {pkg}\n", encoding="utf-8")
    (backend / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")
    (backend / "poetry.lock").write_text("lock-content\n", encoding="utf-8")
    tests = backend / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text("# root conftest\n", encoding="utf-8")
    # Representative group scopes
    for d in (
        "tests/api",
        "tests/runs",
        "tests/core/security",
        "tests/security",
        "tests/tools",
        "tests/agents",
        "tests/brain",
        "tests/unit",
    ):
        (backend / d).mkdir(parents=True, exist_ok=True)
    (tests / "api" / "test_api.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    (tests / "core" / "test_core_a.py").write_text("def test_c():\n    pass\n", encoding="utf-8")
    (tests / "core" / "test_core_rate_limiter.py").write_text(
        "def test_rl():\n    pass\n", encoding="utf-8"
    )
    (tests / "core" / "security" / "test_auth.py").write_text(
        "def test_s():\n    pass\n", encoding="utf-8"
    )
    (tests / "core" / "conftest.py").write_text("# core conftest\n", encoding="utf-8")
    (tests / "test_root_smoke.py").write_text("def test_r():\n    pass\n", encoding="utf-8")
    return backend


def key_for(backend: Path, group: str, paths: str) -> str:
    return ckey.group_cache_key(group, paths, backend)


# ── Determinism & stability ──────────────────────────────────────────────────


def test_same_tree_same_key(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    k1 = key_for(backend, "fast", "tests/api tests/runs")
    k2 = key_for(backend, "fast", "tests/api tests/runs")
    assert k1 == k2
    assert k1.startswith("bcov-v1-fast-")


def test_mtime_touch_does_not_change_key(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    target = backend / "core" / "mod.py"
    k1 = key_for(backend, "fast", "tests/api")
    import os

    os.utime(target, (0, 0))  # change mtime only, not content
    k2 = key_for(backend, "fast", "tests/api")
    assert k1 == k2, "cache keys must be content-derived, not mtime-derived"


def test_different_groups_have_different_keys(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    keys = {
        key_for(backend, g, p)
        for g, p in (
            ("fast", "tests/api tests/runs"),
            ("core_unit", "tests/core --ignore=tests/core/security"),
            ("services", "tests/agents tests/test_*.py"),
        )
    }
    assert len(keys) == 3


# ── Sensitivity (invalidate-on-change contract) ──────────────────────────────


def test_measured_source_change_invalidates_all_groups(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    groups = {
        "fast": "tests/api tests/runs",
        "services": "tests/agents tests/test_*.py",
    }
    before = {g: key_for(backend, g, p) for g, p in groups.items()}
    # Touch a measured package NOT related to either group's tests —
    # invalidate-ALL is the contract (the gate numerator depends on source).
    (backend / "tools" / "mod.py").write_text("# changed\n", encoding="utf-8")
    after = {g: key_for(backend, g, p) for g, p in groups.items()}
    assert before != after
    assert all(before[g] != after[g] for g in groups)


def test_pyproject_change_invalidates(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    k1 = key_for(backend, "fast", "tests/api")
    (backend / "pyproject.toml").write_text("[tool.pytest]\naddopts=[]\n", encoding="utf-8")
    assert key_for(backend, "fast", "tests/api") != k1


def test_lock_change_invalidates(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    k1 = key_for(backend, "services", "tests/agents")
    (backend / "poetry.lock").write_text("lock-content-v2\n", encoding="utf-8")
    assert key_for(backend, "services", "tests/agents") != k1


def test_root_conftest_change_invalidates(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    k1 = key_for(backend, "core_unit", "tests/core --ignore=tests/core/security")
    (backend / "tests" / "conftest.py").write_text("# changed\n", encoding="utf-8")
    assert key_for(backend, "core_unit", "tests/core --ignore=tests/core/security") != k1


def test_group_scope_test_change_invalidates_only_that_group(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    fast_before = key_for(backend, "fast", "tests/api tests/runs")
    services_before = key_for(backend, "services", "tests/agents tests/test_*.py")
    (backend / "tests" / "api" / "test_api.py").write_text(
        "def test_a2():\n    pass\n", encoding="utf-8"
    )
    assert key_for(backend, "fast", "tests/api tests/runs") != fast_before
    assert key_for(backend, "services", "tests/agents tests/test_*.py") == services_before


def test_scoped_conftest_change_invalidates_owner_group(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    fast_paths = "tests/core/security tests/api"
    core_paths = (
        "tests/core --ignore=tests/core/security --ignore=tests/core/test_core_rate_limiter.py"
    )
    fast_before = key_for(backend, "fast", fast_paths)
    core_before = key_for(backend, "core_unit", core_paths)
    (backend / "tests" / "core" / "conftest.py").write_text("# v2\n", encoding="utf-8")
    assert key_for(backend, "fast", fast_paths) != fast_before
    assert key_for(backend, "core_unit", core_paths) != core_before


# ── Scope resolution semantics ───────────────────────────────────────────────


def test_ignore_excludes_files_from_scope(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    with_ignore = ckey.resolve_group_scope(backend, "tests/core --ignore=tests/core/security")
    rels = {p.relative_to(backend).as_posix() for p in with_ignore}
    assert "tests/core/security/test_auth.py" not in rels
    assert "tests/core/test_core_a.py" in rels


def test_root_level_glob_resolves(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    scope = ckey.resolve_group_scope(backend, "tests/agents tests/test_*.py")
    rels = {p.relative_to(backend).as_posix() for p in scope}
    assert "tests/test_root_smoke.py" in rels


def test_py_caches_never_enter_hashes(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    pycache = backend / "core" / "__pycache__"
    pycache.mkdir()
    (pycache / "mod.cpython-313.pyc").write_bytes(b"\x00\x01")
    k1 = key_for(backend, "fast", "tests/api")
    (pycache / "mod.cpython-313.pyc").write_bytes(b"\x00\x02")
    assert key_for(backend, "fast", "tests/api") == k1


def test_missing_poetry_lock_hash_is_stable(tmp_path) -> None:
    backend = build_fake_backend(tmp_path)
    (backend / "poetry.lock").unlink()
    k1 = key_for(backend, "fast", "tests/api")
    k2 = key_for(backend, "fast", "tests/api")
    assert k1 == k2


# ── Contract locks against the live repo ─────────────────────────────────────


# বাংলা মন্তব্য (#2616 triage): ci.yml --cov equivalence-lock টেস্ট মুছে ফেলা
# হলো — .github/workflows/ci.yml (২,০৬৬ লাইন) DRY 3-Pipeline prune (37d6c126)
# এ অবসর নিয়েছে; কোনো workflow আর --cov ম্যাট্রিক্স চালায় না (PR Gate
# --no-cov, coverage-গেট dispatch ম্যাট্রিক্স অবসরপ্রাপ্ত), তাই lock-চুক্তির
# বিষয়বস্তুই আর নেই — অনাথ টেস্ট FileNotFoundError ছুড়ছিল।
# MEASURED_PACKAGES নিজে বহাল (coverage_cache_keys.compute_all_group_keys
# এখনো গ্রুপ-স্কোপ হ্যাশে ব্যবহার করে)।


def test_real_repo_group_scopes_resolve(tmp_path) -> None:
    """The real GROUPS paths resolve to non-empty scopes on the live tree —
    a typo'd group path would silently produce an empty scope hash."""
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))
    import plan_backend_test_groups as planner  # noqa: PLC0415

    for key, (_, paths) in planner.GROUPS.items():
        scope = ckey.resolve_group_scope(REPO_ROOT / "backend", paths)
        assert scope, f"group {key} resolved to an empty scope"
