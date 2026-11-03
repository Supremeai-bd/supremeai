import pytest

from core.startup_validator import StartupValidator


@pytest.mark.anyio
async def test_startup_validator_fails_when_app_name_empty(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "app_name", "", raising=False)

    # Mock at least one API key to pass validation
    monkeypatch.setattr(
        settings.__class__, "openrouter_api_key", property(lambda self: "mock-key"), raising=False
    )

    with pytest.raises(ValueError):
        await StartupValidator.validate()

    st = StartupValidator.last_status()
    assert st["success"] is False


@pytest.mark.anyio
async def test_startup_validator_passes(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "app_name", "SupremeAI", raising=False)
    # Mock at least one API key to pass validation
    monkeypatch.setattr(
        settings.__class__, "openrouter_api_key", property(lambda self: "mock-key"), raising=False
    )
    await StartupValidator.validate()

    st = StartupValidator.last_status()
    assert st["success"] is True
