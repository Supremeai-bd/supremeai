"""Tests for core.ld_client — LaunchDarkly client init gracefully degrades when SDK absent."""

from core import ld_client


def test_module_level_client_is_none_when_unsupported():
    # In the light test env the LaunchDarkly SDK is not installed, so the
    # module-level client is None.
    assert ld_client.ld_ai_client is None


def test_init_ld_client_returns_none_when_unsupported(monkeypatch):
    monkeypatch.setattr(ld_client, "LD_SUPPORTED", False)
    assert ld_client.init_ld_client() is None


def test_get_ld_ai_components_returns_none_tuple():
    result = ld_client.get_ld_ai_components()
    assert result == (None, None, None, None, None)
