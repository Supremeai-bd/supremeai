from unittest.mock import MagicMock
from tools.vpn_switcher import VPNRotator


def _make_rotator():
    rotator = VPNRotator.__new__(VPNRotator)
    rotator.endpoints = ["ep1", "ep2"]
    rotator.current_index = 0
    rotator.history = []
    rotator.max_history = 100
    return rotator


def test_rotate_cycles_endpoints():
    r = _make_rotator()
    first = r.rotate()
    assert first["rotated"] is True
    assert first["endpoint"] == "ep1"
    second = r.rotate()
    assert second["endpoint"] == "ep2"
    third = r.rotate()
    assert third["endpoint"] == "ep1"


def test_current_reflects_next_endpoint():
    r = _make_rotator()
    r.rotate()
    assert r.current() == "ep2"


def test_rotate_agent_records_rotation():
    r = _make_rotator()
    result = r.rotate_agent("agent-1")
    assert result["agent_id"] == "agent-1"
    assert "endpoint" in result
    assert result["rotated"] is True


def test_configure_endpoints_resets_index():
    r = _make_rotator()
    r.rotate()
    res = r.configure_endpoints(["a", "b", "c"])
    assert res["count"] == 3
    assert r.current() == "a"


def test_add_endpoint_rejects_duplicates():
    r = _make_rotator()
    res = r.add_endpoint("ep1")
    assert res["added"] is False
    assert res["reason"] == "duplicate endpoint"
