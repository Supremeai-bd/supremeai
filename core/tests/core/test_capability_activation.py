from core.capability_activation import CapabilityActivationStore


def test_core_capability_is_enabled_for_every_tenant():
    store = CapabilityActivationStore()
    assert store.is_enabled("tenant-a", "system.health.read") is True


def test_optional_capability_requires_explicit_tenant_activation():
    store = CapabilityActivationStore()
    assert store.is_enabled("tenant-a", "work.projects.read") is False
    store.enable("tenant-a", "work.projects.read")
    assert store.is_enabled("tenant-a", "work.projects.read") is True
    store.disable("tenant-a", "work.projects.read")
    assert store.is_enabled("tenant-a", "work.projects.read") is False
