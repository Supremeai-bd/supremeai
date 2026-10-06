"""Tests for core.feature_flags — pure env-var + percentage rollout logic (no DB required)."""

import pytest

from core import feature_flags as ff_module
from core.feature_flags import FeatureFlags, feature_flags


@pytest.fixture(autouse=True)
def clear_cache():
    feature_flags.reset_cache()
    yield
    feature_flags.reset_cache()


def test_env_flag_truthy(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "true")
    assert ff_module._env_flag("SUPREMEAI_MEM0_ENABLED") is True
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "1")
    assert ff_module._env_flag("SUPREMEAI_MEM0_ENABLED") is True


def test_env_flag_tri_state(monkeypatch):
    """Issue #1818 bug-2: _env_flag is tri-state — None when unset, so an
    explicit env kill-switch can be distinguished from "not configured"."""
    monkeypatch.delenv("SUPREMEAI_MEM0_ENABLED", raising=False)
    assert ff_module._env_flag("SUPREMEAI_MEM0_ENABLED") is None
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "")
    assert ff_module._env_flag("SUPREMEAI_MEM0_ENABLED") is None
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "no")
    assert ff_module._env_flag("SUPREMEAI_MEM0_ENABLED") is False


def test_mem0_enabled_reads_env(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "yes")
    assert feature_flags.mem0_enabled() is True


def test_all_flag_accessors(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_GRAPHITI_ENABLED", raising=False)
    monkeypatch.delenv("SUPREMEAI_E2B_ENABLED", raising=False)
    assert feature_flags.graphiti_enabled() is False
    # (#4068) retired flags — absence is the contract
    assert not hasattr(feature_flags, "browser_use_enabled")
    assert feature_flags.e2b_enabled() is False
    assert not hasattr(feature_flags, "openhands_enabled")


def test_cache_is_used(monkeypatch):
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "true")
    assert feature_flags.mem0_enabled() is True
    # Flip env; cached value should still be returned until reset.
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "false")
    assert feature_flags.mem0_enabled() is True
    feature_flags.reset_cache()
    assert feature_flags.mem0_enabled() is False


def test_db_flag_true_path(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_MEM0_ENABLED", raising=False)
    feature_flags.reset_cache()
    monkeypatch.setattr(ff_module, "_db_flag", lambda name, user_id=None: True)
    assert feature_flags.mem0_enabled(user_id="u1") is True


def test_db_flag_unreachable_returns_none(monkeypatch):
    monkeypatch.delenv("SUPREMEAI_MEM0_ENABLED", raising=False)
    feature_flags.reset_cache()
    monkeypatch.setattr(ff_module, "_db_flag", lambda name, user_id=None: None)
    assert feature_flags.mem0_enabled() is False


def test_is_enabled_full_and_off():
    assert FeatureFlags.is_enabled("adv.i18n_ai_translate") is True
    assert FeatureFlags.is_enabled("nonexistent.flag") is False


def test_is_enabled_partial_rollout(monkeypatch):
    monkeypatch.setattr(FeatureFlags, "ADV_FLAGS", {"adv.x": {"enabled": True, "pct": 0}})
    assert FeatureFlags.is_enabled("adv.x") is False
    monkeypatch.setattr(FeatureFlags, "ADV_FLAGS", {"adv.y": {"enabled": True, "pct": 40}})
    # With pct=40, bucket = abs(hash(user_id)) % 100 < 40 — exercise deterministic path.
    result_a = FeatureFlags.is_enabled("adv.y", user_id="alpha")
    result_b = FeatureFlags.is_enabled("adv.y", user_id="alpha")
    assert result_a == result_b  # deterministic


def test_status_structure():
    status = feature_flags.status()
    assert set(status) == {
        "mem0",
        "graphiti",
        "e2b",
        "advanced_rollout",
    }


def test_env_false_beats_db_true_acceptance(monkeypatch):
    """Issue #1818 acceptance criterion: env=false + db=true → False.

    The documented env-first contract: an explicit env kill-switch must
    stick even when the DB row is enabled.
    """
    monkeypatch.setenv("SUPREMEAI_MEM0_ENABLED", "false")
    feature_flags.reset_cache()
    monkeypatch.setattr(ff_module, "_db_flag", lambda name, user_id=None: True)
    assert feature_flags.mem0_enabled() is False


def test_env_unset_db_true_enables(monkeypatch):
    """Issue #1818: env unset → DB tier decides (true row enables)."""
    monkeypatch.delenv("SUPREMEAI_MEM0_ENABLED", raising=False)
    feature_flags.reset_cache()
    monkeypatch.setattr(ff_module, "_db_flag", lambda name, user_id=None: True)
    assert feature_flags.mem0_enabled() is True


def test_db_lookup_uses_runtime_flag_name(monkeypatch):
    """Issue #1818 acceptance criterion: flag names unified — the real DB
    wrapper receives the canonical feature_name key ('mem0_enabled'), not
    the env var name (bug-1 path: db.is_feature_enabled on the WRAPPER)."""
    monkeypatch.delenv("SUPREMEAI_MEM0_ENABLED", raising=False)
    feature_flags.reset_cache()
    seen: dict = {}

    class FakeDB:
        def is_feature_enabled(self, feature_name, user_id=None):
            seen["name"] = feature_name
            return False

    import database.supabase_client as supabase_module

    monkeypatch.setattr(supabase_module, "db", FakeDB())
    assert feature_flags.mem0_enabled() is False
    assert seen["name"] == "mem0_enabled"
