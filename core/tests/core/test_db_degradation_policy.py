"""P1 — Role-aware DB degradation policy tests.

বাংলা: core = DB ফেলে NOT READY (production); worker/scraper/mcp =
role-specific degradation allowed; dev/local core-এ flag দিলে convenience।
"""

from core.health_policy import db_failure_readiness, is_critical_db_check

# ---------------------------------------------------------------------------
# core role (and unset) — the strict contract
# ---------------------------------------------------------------------------


def test_core_production_db_failure_is_not_ready_even_with_flag():
    ready, reason = db_failure_readiness("core", "production", degradation_requested=True)
    assert ready is False
    assert "IGNORED" in reason  # flag must be loudly ignored, not silently honored


def test_core_staging_db_failure_is_not_ready_even_with_flag():
    ready, _ = db_failure_readiness("core", "staging", degradation_requested=True)
    assert ready is False


def test_core_unset_role_treated_as_core():
    ready, _ = db_failure_readiness("", "production", degradation_requested=True)
    assert ready is False


def test_core_no_flag_no_readiness():
    ready, _ = db_failure_readiness("core", "production", degradation_requested=False)
    assert ready is False


def test_core_dev_degradation_allowed_when_flag_set():
    for env in ("local", "dev", "development", "test"):
        ready, reason = db_failure_readiness("core", env, degradation_requested=True)
        assert ready is True, env
        assert "dev degradation" in reason


def test_core_dev_without_flag_still_not_ready():
    ready, _ = db_failure_readiness("core", "local", degradation_requested=False)
    assert ready is False


# ---------------------------------------------------------------------------
# worker / scraper / mcp — role-specific degradation allowed everywhere
# ---------------------------------------------------------------------------


def test_worker_scraper_mcp_degrade_in_production():
    for role in ("worker", "scraper", "mcp"):
        ready, reason = db_failure_readiness(role, "production", degradation_requested=False)
        assert ready is True, role
        assert "role-specific" in reason


def test_worker_degrades_even_with_flag_and_any_env():
    for env in ("production", "staging", "local", "test"):
        ready, _ = db_failure_readiness("worker", env, degradation_requested=True)
        assert ready is True, env


def test_unknown_role_falls_back_to_core_strictness():
    ready, _ = db_failure_readiness("unknown-role", "production", degradation_requested=True)
    assert ready is False


# ---------------------------------------------------------------------------
# criticality mapping
# ---------------------------------------------------------------------------


def test_criticality_matches_policy():
    assert is_critical_db_check("core") is True
    assert is_critical_db_check("") is True
    assert is_critical_db_check(None) is True
    for role in ("worker", "scraper", "mcp"):
        assert is_critical_db_check(role) is False, role
