"""Smoke tests for config_classification canonical/alias resolution."""
import pytest

from core.config_classification import (
    ALIAS_TO_CANONICAL,
    BY_NAME,
    all_config_names,
    canonical_name,
    get_config_spec,
)


def test_canonical_name_resolves_alias():
    assert canonical_name("RENDER_PRIMARY_SVC_ID") == "RENDER_CORE_SERVICE_ID"
    assert canonical_name("RENDER_MCP_SVC_ID") == "RENDER_MCP_SERVICE_ID"
    assert canonical_name("RENDER_CORE_SERVICE_ID") == "RENDER_CORE_SERVICE_ID"


def test_get_config_spec_resolves_alias():
    spec = get_config_spec("RENDER_PRIMARY_SVC_ID")
    assert spec is not None
    assert spec.name == "RENDER_CORE_SERVICE_ID"
    spec2 = get_config_spec("RENDER_CORE_SERVICE_ID")
    assert spec2 is not None
    assert spec2.name == "RENDER_CORE_SERVICE_ID"


def test_alias_registered_in_alias_map():
    assert "RENDER_PRIMARY_SVC_ID" in ALIAS_TO_CANONICAL
    assert ALIAS_TO_CANONICAL["RENDER_PRIMARY_SVC_ID"] == "RENDER_CORE_SERVICE_ID"


def test_all_config_names_includes_canonical():
    names = all_config_names()
    assert "RENDER_CORE_SERVICE_ID" in names
    assert "RENDER_MCP_SERVICE_ID" in names


def test_by_name_count_matches_specs():
    from core.config_classification import CONFIG_SPECS

    assert len(BY_NAME) == len(CONFIG_SPECS)
