from core.capability_discovery import discover_capabilities, discover_capability
from core.capability_gateway import HEALTH_CAPABILITY


def test_discovery_reports_tenant_aware_health_capability():
    item = discover_capability(HEALTH_CAPABILITY, "tenant-a")
    assert item is not None
    assert item["enabled"] is True
    assert item["circle"] == "gateway"


def test_discovery_only_returns_registered_capabilities():
    names = {item["name"] for item in discover_capabilities("tenant-a")}
    assert HEALTH_CAPABILITY in names
