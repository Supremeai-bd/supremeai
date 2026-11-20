"""Tests for the guard inventory (no guard may exist without a caller).

The inventory exists because 94 guard-named modules were reachable from neither a
workflow nor the roster on 2026-11-20. These tests pin the behaviour that made
that visible — especially the *derived* classification, since a hand-maintained
list of guards would rot exactly like the roster did.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.ci import guard_inventory as gi  # noqa: E402


def test_guard_classification_is_name_or_self_advertised(tmp_path: Path):
    """Derived, not listed: a new guard needs no edit here."""
    named = tmp_path / "something_guard.py"
    named.write_text("print('hi')\n")
    assert gi.is_guard(named), "a *_guard.py must classify as a guard"

    checker = tmp_path / "verify_things.py"
    checker.write_text('"""usage: --check"""\n')
    assert gi.is_guard(checker), "a module advertising --check must classify as a guard"

    library = tmp_path / "helper.py"
    library.write_text("def add(a, b):\n    return a + b\n")
    assert not gi.is_guard(library), "a plain library must not be treated as a guard"


def test_real_repo_guards_are_classified():
    guards = {p.name for p in gi.CI_DIR.glob("*.py") if gi.is_guard(p)}
    assert "architecture_gap_guardian.py" in guards
    assert "guard_inventory.py" in guards
    assert "wiring_integrity_guard.py" in guards


def test_inventory_finds_callers_from_the_roster_and_workflows():
    called = gi.callers()
    assert "run_all_guards.py" in called.get("architecture_gap_guardian.py", []), (
        "the guardian is in the roster; the inventory must see that"
    )
    # At least one guard is wired through a workflow rather than the roster.
    wf_wired = [n for n, w in called.items() if any(".github/workflows" in x for x in w)]
    assert wf_wired, "no guard detected as workflow-wired"


def test_scan_partitions_wired_and_orphans_disjointly():
    orphans, wired, called = gi.scan()
    assert set(orphans).isdisjoint(set(wired)), "a guard cannot be both"
    # ``callers()`` deliberately also reports non-guard scripts (it is a raw map
    # of "who invokes what"), so the identity is: every *guard* is either wired
    # or orphaned, and every wired entry is a guard.
    guards = {p.name for p in gi.CI_DIR.glob("*.py") if gi.is_guard(p)}
    assert set(wired) | set(orphans) == guards
    assert set(wired) <= set(called)
    assert set(guards) <= set(called) | set(orphans)


def test_register_is_valid_json_with_reasons():
    register = gi.load_register()
    known = register.get("known_orphans", {})
    assert isinstance(known, dict)
    for name, reason in known.items():
        assert name.endswith(".py"), f"register entry {name!r} is not a module"
        assert reason and len(reason) > 10, f"{name} has no recorded reason"


def test_register_entries_are_really_orphans_or_already_wired():
    """The register must not carry stale entries.

    A wired guard still listed as an orphan hides that it is now enforced — and
    the register is a ratchet, so shrinking it is the goal.
    """
    orphans, wired, _ = gi.scan()
    known = set(gi.load_register().get("known_orphans", {}))
    stale = known & set(wired)
    assert not stale, (
        f"these guards are wired but still frozen as orphans: {sorted(stale)}. "
        "Run `python scripts/ci/guard_inventory.py --baseline` to shrink the register."
    )
    unexpected = set(orphans) - known
    assert not unexpected, f"unregistered orphans: {sorted(unexpected)}"


def test_check_mode_fails_on_a_new_unregistered_orphan(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gi, "CI_DIR", tmp_path)
    monkeypatch.setattr(gi, "REGISTER", tmp_path / "register.json")
    monkeypatch.setattr(gi, "ROSTER", tmp_path / "roster.py")
    monkeypatch.setattr(gi, "WORKFLOW_DIR", tmp_path / "wf")
    (tmp_path / "wf").mkdir()
    (tmp_path / "brand_new_guard.py").write_text("print('unwired')\n")
    (tmp_path / "roster.py").write_text("GUARDS = []\n")

    assert gi.main(["--check"]) == 1, "an unregistered orphan must fail the check"


def test_baseline_mode_records_orphans(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gi, "CI_DIR", tmp_path)
    monkeypatch.setattr(gi, "REGISTER", tmp_path / "register.json")
    monkeypatch.setattr(gi, "ROSTER", tmp_path / "roster.py")
    monkeypatch.setattr(gi, "WORKFLOW_DIR", tmp_path / "wf")
    (tmp_path / "wf").mkdir()
    (tmp_path / "lonely_guard.py").write_text("print('x')\n")
    (tmp_path / "roster.py").write_text("GUARDS = []\n")

    assert gi.main(["--baseline"]) == 0
    written = json.loads((tmp_path / "register.json").read_text())
    assert "lonely_guard.py" in written["known_orphans"]
    # And once frozen, --check passes.
    assert gi.main(["--check"]) == 0


def test_check_passes_on_the_current_tree():
    """The repo must be green right now; otherwise the roster entry is dead weight."""
    assert gi.main(["--check"]) == 0
