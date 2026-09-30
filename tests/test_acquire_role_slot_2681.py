"""#2681 Finding-1 — acquire_role_slot: registry-driven lanes + workload ranking.

Locked contracts:
- Registry (AGENT_SLOT_REGISTRY.yaml v2.2) pools with branch slots extend the
  hardcoded lane set (union — built-in 5 unchanged).
- `super` is explicit-only (guardrail: never auto-inferred from titles).
- `infer_role_from_context` stays backward-compatible (first-match single role).
- `select_least_loaded_role` ranks multi-candidate lanes by busy-slot count
  (ties → candidate order); single candidate = zero extra fetches.
- Registry/corrupt-file failure falls back to static behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# বাংলা মন্তব্য: স্ক্রিপ্ট standalone — agents ডিরেক্টরি path-এ যোগ করে ইমপোর্ট।
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "agents"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import acquire_role_slot as m


@pytest.fixture(autouse=True)
def _reset_registry_cache():
    m._REGISTRY_LANE_CACHE = None
    yield
    m._REGISTRY_LANE_CACHE = None


def test_registry_lanes_discovered():
    """বাংলা মন্তব্য: registry-র branch-slotted pool গুলো আবিষ্কৃত হয়।"""
    lanes = m.load_registry_lanes()
    assert "browser" in lanes and "super" in lanes
    assert "{N}" in lanes["browser"]


def test_valid_roles_is_union():
    roles = m.get_valid_roles()
    # বাংলা মন্তব্য: পুরোনো ৫টি অর্ডার-অক্ষত + registry-র নতুনগুলো পরে।
    assert roles[:5] == ("planner", "coder", "pr-helper", "ci", "platform")
    assert "browser" in roles and "super" in roles


def test_registry_corrupt_falls_back_static():
    """Registry পড়তে ব্যর্থ → খালি lanes, static আচরণ (backward-compat)।"""
    with patch.object(Path, "read_text", side_effect=OSError("missing")):
        m._REGISTRY_LANE_CACHE = None
        assert m.load_registry_lanes() == {}
        assert m.infer_role_from_context(title="fix the bug") == "coder"
    m._REGISTRY_LANE_CACHE = None


def test_super_never_auto_inferred():
    """Guardrail: super union lane কেবল explicit — title-pattern থেকে নয়।"""
    assert m.infer_role_candidates(title="super agent omni-lane work") == ["coder"]
    assert m.infer_role_candidates(explicit_role="super") == ["super"]


def test_browser_lane_from_registry_label_and_pattern():
    assert m.infer_role_candidates(labels=["handoff:browser"]) == ["browser"]
    assert "browser" in m.infer_role_candidates(
        title="run browser E2E exploration and playwright check"
    )


def test_wrapper_backward_compatible_first_match():
    assert m.infer_role_from_context(title="audit the architecture") == "planner"
    assert m.infer_role_from_context(explicit_role="coder") == "coder"


def test_select_least_loaded_ranks_by_busy_count():
    """বাংলা মন্তব্য: কম-ব্যস্ত lane আগে — টাই-তে প্রার্থী-ক্রম।"""
    with (
        patch.object(m, "fetch_open_prs_head_branches", return_value=set()),
        patch.object(m, "fetch_in_progress_issues_by_slot", return_value={}),
        patch.object(m, "fetch_active_mesh_heartbeats", return_value=set()),
        patch.object(
            m,
            "fetch_existing_role_branches",
            side_effect=lambda role, repo_dir=None: (
                [1, 2] if role == "coder" else ([1] if role == "browser" else [])
            ),
        ),
    ):
        picked = m.select_least_loaded_role(["coder", "browser", "ci"])
    assert picked == "ci"  # coder=2 busy, browser=1, ci=0


def test_select_least_loaded_tie_keeps_candidate_order():
    with (
        patch.object(m, "fetch_open_prs_head_branches", return_value=set()),
        patch.object(m, "fetch_in_progress_issues_by_slot", return_value={}),
        patch.object(m, "fetch_active_mesh_heartbeats", return_value=set()),
        patch.object(m, "fetch_existing_role_branches", return_value=[]),
    ):
        assert m.select_least_loaded_role(["ci", "browser"]) == "ci"  # টাই → আগের প্রার্থী


def test_select_single_candidate_zero_fetch():
    """এক প্রার্থী = কোনো occupancy fetch নয় (zero-overhead path)।"""
    with patch.object(m, "fetch_open_prs_head_branches") as f1:
        assert m.select_least_loaded_role(["coder"]) == "coder"
        f1.assert_not_called()
