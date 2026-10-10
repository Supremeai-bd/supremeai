# backend/tests/core/test_provider_registry.py
"""#3214 — runtime provider registry tests (AC-1..AC-7)।

সব টেস্ট offline: registry raw key value জানে না, network ছোঁয় না।
বিদ্যমান static maps (groq/openai — যাচাইকৃত সদস্য) ব্যবহার করে।
"""

from __future__ import annotations

import pytest

from core.llm.provider_registry import (
    Capability,
    CredentialDescriptor,
    ModelDescriptor,
    NoCompatibleProviderError,
    ProviderDescriptor,
    ProviderHealth,
    ProviderRegistry,
)


def _models() -> dict[str, tuple[str, frozenset[Capability]]]:
    return {
        "groq/test-a": ("groq", frozenset({Capability.TEXT, Capability.REASONING})),
        "groq/test-vision": ("groq", frozenset({Capability.VISION})),
        "openai/test-b": (
            "openai",
            frozenset({Capability.TEXT, Capability.REASONING, Capability.EMBEDDING}),
        ),
    }


# ---- AC-1: স্বাধীন representation -------------------------------------


def test_ac1_credential_provider_model_capability_independent() -> None:
    cred = CredentialDescriptor(provider="groq", settings_attr="groq_api_key")
    model = ModelDescriptor(
        model="groq/test-a",
        provider="groq",
        capabilities=frozenset({Capability.TEXT}),
    )
    reg = ProviderRegistry(_models())
    prov = reg.select(Capability.TEXT).provider
    # চারটি স্বতন্ত্র ধারণা — কোনোটা অন্যটার ভেতরে গলে যায় না।
    assert prov.credential == cred
    assert model.provider == "groq"  # F841-শাসন: ঘোষিত descriptor-ই প্রমাণ
    assert reg.select(Capability.TEXT).model.provider == model.provider
    assert isinstance(prov, ProviderDescriptor)
    assert Capability.TEXT.value == "text"


# ---- AC-2: adapter isolation -------------------------------------------


def test_ac2_selection_is_descriptor_not_sdk_object() -> None:
    sel = ProviderRegistry(_models()).select(Capability.EMBEDDING)
    assert isinstance(sel.model, ModelDescriptor)
    assert not hasattr(sel, "client") and not hasattr(sel, "sdk")
    # Selection শুধু descriptor বহন করে — vendor পার্থক্য adapter-স্তরেই থাকে।
    assert sel.model.provider == "openai"


# ---- AC-3: runtime disable, কোড পরিবর্তন ছাড়া --------------------------


def test_ac3_mark_unavailable_then_available_roundtrip() -> None:
    reg = ProviderRegistry(_models())
    reg.mark_unavailable("groq", "invalid credential (401)")
    with pytest.raises(NoCompatibleProviderError):
        reg.select(Capability.VISION)  # শুধু groq-ই vision দেয়
    reg.mark_available("groq")
    assert reg.select(Capability.VISION).provider.name == "groq"


def test_ac3_unknown_provider_and_empty_reason_fail_honest() -> None:
    reg = ProviderRegistry(_models())
    with pytest.raises(KeyError):
        reg.mark_unavailable("nope", "x")
    with pytest.raises(ValueError):
        reg.mark_unavailable("groq", "   ")


# ---- AC-4: healthy alternate স্বয়ংক্রিয় নির্বাচন ------------------------


def test_ac4_alternate_provider_selected_when_primary_down() -> None:
    reg = ProviderRegistry(_models())
    reg.mark_unavailable("groq", "outage")
    sel = reg.select(Capability.REASONING)
    assert sel.provider.name == "openai"  # policy-permitted fallback
    assert sel.model.model == "openai/test-b"


# ---- AC-5: retired model structured state ------------------------------


def test_ac5_retired_model_excluded_and_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("core.llm.provider_registry._RETIRED_MODELS", {"openai/test-b"})
    reg = ProviderRegistry(_models())
    with pytest.raises(NoCompatibleProviderError) as err:
        reg.select(Capability.EMBEDDING)
    assert "retired" in err.value.evidence["openai/test-b"]
    snap = reg.health_snapshot()
    assert snap["model:openai/test-b"] == "retired"


# ---- AC-6: raw key কখনো ধরা/প্রকাশ হয় না -------------------------------


def test_ac6_only_attr_names_stored_never_values() -> None:
    reg = ProviderRegistry(_models())
    sel = reg.select(Capability.TEXT)
    blob = f"{sel!r}{sel.provider!r}{reg.health_snapshot()}"
    assert "groq_api_key" in blob  # attr-নাম আছে
    assert "gsk_" not in blob and "sk-" not in blob  # key-শেপের value নেই
    # জাল key value ঢুকিয়েও registry তা ধরে না:
    reg.mark_unavailable("groq", "gsk_FAKE_SECRET_VALUE leaked")
    err = None
    try:
        reg.select(Capability.REASONING, exclude_models={"openai/test-b"})
    except NoCompatibleProviderError as exc:  # pragma: no cover - guard
        err = exc
    assert err is not None and "gsk_FAKE_SECRET_VALUE" in str(err)
    # কিন্তু snapshot-এ কারণ-মান যায় না (শুধু অবস্থা):
    assert "gsk_FAKE_SECRET_VALUE" not in str(reg.health_snapshot())


# ---- AC-7: fallback পরিবার ---------------------------------------------


def test_ac7_success_path_deterministic() -> None:
    reg = ProviderRegistry(_models())
    first = reg.select(Capability.TEXT)
    second = reg.select(Capability.TEXT)
    assert (first.model.model, first.provider.name) == (
        second.model.model,
        second.provider.name,
    )


def test_ac7_invalid_key_then_quota_then_outage_all_skip() -> None:
    reg = ProviderRegistry(_models())
    reg.mark_unavailable("groq", "invalid key (401)")
    reg.mark_unavailable("openai", "quota exhausted (429)")
    with pytest.raises(NoCompatibleProviderError) as err:
        reg.select(Capability.TEXT)
    assert err.value.evidence == {
        "groq/test-a": "invalid key (401)",
        "openai/test-b": "quota exhausted (429)",
    }


def test_ac7_incompatible_capability_structured_failure() -> None:
    reg = ProviderRegistry(_models())
    with pytest.raises(NoCompatibleProviderError) as err:
        reg.select(Capability.VISION, exclude_models={"groq/test-vision"})
    assert err.value.capability is Capability.VISION
    assert err.value.evidence == {"groq/test-vision": "excluded"}


def test_ac7_unknown_provider_in_declaration_rejected() -> None:
    with pytest.raises(ValueError, match="without credentials"):
        ProviderRegistry({"ghost/model": ("ghost", frozenset({Capability.TEXT}))})


def test_ac7_health_snapshot_shape() -> None:
    reg = ProviderRegistry(_models())
    reg.mark_unavailable("openai", "provider outage")
    snap = reg.health_snapshot()
    assert snap["groq"] == ProviderHealth.AVAILABLE.value
    assert snap["openai"] == ProviderHealth.UNAVAILABLE.value
