"""Phase 0.4 hard-cut guard: the dead HF tiny-brain probe must stay cut (Rule 12).

The HF space `njelitltd-tiny-brain.hf.space` is dead; health endpoints must not
probe it. `scripts/ci/tiny_brain_pr_guard.py` remains untouched (separate lane).
"""

from __future__ import annotations

from pathlib import Path

ENDPOINTS_HEALTH = Path("core/api/routes/admin_dashboard/endpoints_health.py")
GENERATOR = Path("core/scripts/tiny_brain_dataset_generator.py")


def test_dead_hf_probe_is_gone():
    assert not GENERATOR.exists(), "5-seed tiny-brain dataset generator was hard-cut (Rule 12)"
    src = ENDPOINTS_HEALTH.read_text(encoding="utf-8")
    assert "hf.space" not in src
    assert "TINY_BRAIN_URL" not in src
    assert "/shadow-hf/status" not in src
    assert "/shadow-hf/top-ai-refresh" not in src


def test_disabled_kaggle_stub_and_health_map_survive():
    src = ENDPOINTS_HEALTH.read_text(encoding="utf-8")
    assert "/shadow-hf/kaggle-rotate" not in src  # dead stub cut (Rule 12)
    assert "/health-map" in src
    assert "import httpx" not in src  # no network client left behind unused
