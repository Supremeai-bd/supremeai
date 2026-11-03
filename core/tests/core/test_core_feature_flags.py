# tests/test_core_feature_flags.py
"""Tests for the core feature_flags checker (env-var + percentage rollout paths)."""

import os
from unittest.mock import patch

import pytest

from core import feature_flags as ff


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "TRUE"])
def test_env_flag_truthy_variants(val):
    with patch.dict(os.environ, {ff.MEM0_FLAG: val}):
        f = ff.FeatureFlags()
        f.reset_cache()
        assert f.mem0_enabled() is True


def test_env_flag_falsy_falls_to_db_none():
    with patch.dict(os.environ, {ff.MEM0_FLAG: "false"}):
        f = ff.FeatureFlags()
        f.reset_cache()
        with patch.object(ff, "_db_flag", return_value=None):
            assert f.mem0_enabled() is False


def test_env_flag_empty_falls_to_db_none():
    with patch.dict(os.environ, {ff.MEM0_FLAG: ""}):
        f = ff.FeatureFlags()
        f.reset_cache()
        with patch.object(ff, "_db_flag", return_value=None):
            assert f.mem0_enabled() is False


def test_db_fallback_true_when_env_unset():
    with patch.dict(os.environ, {ff.MEM0_FLAG: ""}):
        f = ff.FeatureFlags()
        f.reset_cache()
        with patch.object(ff, "_db_flag", return_value=True):
            assert f.mem0_enabled() is True


def test_all_integration_flags_default_false_without_db():
    with patch.dict(os.environ, {}, clear=True):
        f = ff.FeatureFlags()
        f.reset_cache()
        with patch.object(ff, "_db_flag", return_value=None):
            assert f.mem0_enabled() is False
            assert f.graphiti_enabled() is False
            # (#4068) browser_use + openhands flags retired — absence is the contract
            assert not hasattr(f, "browser_use_enabled")
            assert f.e2b_enabled() is False
            assert not hasattr(f, "openhands_enabled")


def test_is_enabled_full_rollout():
    assert ff.FeatureFlags.is_enabled("adv.i18n_ai_translate") is True


def test_is_enabled_unknown_flag_false():
    assert ff.FeatureFlags.is_enabled("unknown.flag") is False


def test_is_enabled_percentage_deterministic():
    ff.FeatureFlags.ADV_FLAGS["_test_pct"] = {"enabled": True, "pct": 50}
    try:
        r1 = ff.FeatureFlags.is_enabled("_test_pct", user_id="user123")
        r2 = ff.FeatureFlags.is_enabled("_test_pct", user_id="user123")
        assert r1 == r2
    finally:
        del ff.FeatureFlags.ADV_FLAGS["_test_pct"]


def test_status_returns_expected_keys():
    f = ff.FeatureFlags()
    status = f.status()
    expected = {"mem0", "graphiti", "e2b", "advanced_rollout"}
    assert expected.issubset(set(status.keys()))
