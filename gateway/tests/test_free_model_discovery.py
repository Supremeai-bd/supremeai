"""test_free_model_discovery.py — per-key free-model discovery regression tests.

Locks in the 2026-11-16 fixes:
- A 402 (payment required) on one aggregator model must NOT mark the whole key dead;
  discovery must keep probing and pick the working free model (kilo: efficient=402, free=200).
- Free/preferred models are probed before paid ones so a paid entry cannot shadow them.
- A 401/403 still marks the key dead (auth/forbidden).
"""
import pytest
from unittest.mock import AsyncMock, patch

import gateway.service.free_model_discovery as fmd
from gateway.service.pool import KeySlot


def _slot(provider="kilo", name="KILO_API_KEY"):
    return KeySlot(name=name, key="test-key", provider=provider)


async def _validate_with(slot, fetch, probe):
    """Run validate_slot with model-list + probe + redis mocked out."""
    with patch.object(fmd, "_fetch_model_ids", side_effect=fetch), \
         patch.object(fmd, "_probe_model", side_effect=probe), \
         patch.object(fmd, "_redis_get", new=AsyncMock(return_value=None)), \
         patch.object(fmd, "_redis_set", new=AsyncMock(return_value=None)):
        await fmd.validate_slot(slot)


@pytest.mark.asyncio
async def test_402_on_paid_model_does_not_kill_key():
    """kilo: paid model->402 must be skipped; concrete :free model->200 must be chosen; key stays alive."""
    slot = _slot()

    async def fake_fetch(provider, base_url, api_key):
        return ["kilo-auto/efficient", "nvidia/nemotron-3.5-lightning:free"]

    async def fake_probe(provider, base_url, api_key, model):
        if model == "kilo-auto/efficient":
            return (False, 120.0, 402)   # paid model -> skip, not dead
        return (True, 90.0, 200)          # concrete free model -> works

    await _validate_with(slot, fake_fetch, fake_probe)

    assert slot.cooldown_until == 0.0, "key must NOT be cooled down (402 != dead)"
    assert slot.preferred_model == "nvidia/nemotron-3.5-lightning:free"
    assert "nvidia/nemotron-3.5-lightning:free" in slot.discovered_models
    assert "kilo-auto/efficient" not in slot.discovered_models


@pytest.mark.asyncio
async def test_free_model_probed_before_paid():
    """Free models must be ordered ahead of paid ones regardless of /models order."""
    slot = _slot()
    probed = []

    async def fake_fetch(provider, base_url, api_key):
        # paid model listed first, free second
        return ["kilo-auto/efficient", "baidu/ernie-5.5-flash-preview:free"]

    async def fake_probe(provider, base_url, api_key, model):
        probed.append(model)
        if model.endswith(":free"):
            return (True, 80.0, 200)
        return (False, 100.0, 402)

    await _validate_with(slot, fake_fetch, fake_probe)

    assert probed[0].endswith(":free"), f"free model must be probed first, got {probed}"
    assert slot.preferred_model == "baidu/ernie-5.5-flash-preview:free"


@pytest.mark.asyncio
async def test_401_marks_key_dead():
    """A 401 (invalid token) must still cool the key down for an hour."""
    slot = _slot()

    async def fake_fetch(provider, base_url, api_key):
        return ["some-model"]

    async def fake_probe(provider, base_url, api_key, model):
        return (False, 50.0, 401)

    await _validate_with(slot, fake_fetch, fake_probe)

    assert slot.cooldown_until > 0, "401 must mark the key dead"
    assert slot.discovered_models == []


def test_extract_free_aggregator_model_excludes_paid_and_meta_routers():
    """Paid models, meta-routers (kilo-auto/free, openrouter/free), and non-chat models must be excluded."""
    assert fmd._extract_free_aggregator_model({"id": "kilo-auto/free", "pricing": {"prompt": "0", "completion": "0"}}) is None
    assert fmd._extract_free_aggregator_model({"id": "openrouter/free", "pricing": {"prompt": "0", "completion": "0"}}) is None
    assert fmd._extract_free_aggregator_model({"id": "kilo-auto/efficient", "pricing": {"prompt": "0.001", "completion": "0.002"}}) is None
    assert fmd._extract_free_aggregator_model({"id": "anthropic/claude-opus-5.5", "pricing": {"prompt": "0.015", "completion": "0.075"}}) is None
    assert fmd._extract_free_aggregator_model({"id": "google/lyria-3-pro-preview", "pricing": {"prompt": "0", "completion": "0"}}) is None
    assert fmd._extract_free_aggregator_model({"id": "nvidia/nemotron-3.5-lightning:free", "pricing": {"prompt": "0", "completion": "0"}}) == "nvidia/nemotron-3.5-lightning:free"
    assert fmd._extract_free_aggregator_model("cohere/north-mini-code:free") == "cohere/north-mini-code:free"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])