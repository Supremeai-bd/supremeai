"""VPNRotator (tools/security_tools/vpn_switcher.py) এর ইউনিট টেস্ট।

বাংলা: এন্ডপয়েন্ট রোটেশন ও হিস্ট্রি লজিক কভার করা হয়েছে (নেটওয়ার্ক-ফ্রি)।
"""

from __future__ import annotations

from tools.security_tools.vpn_switcher import VPNRotator


def test_rotate_without_endpoints():
    r = VPNRotator(endpoints=[])
    res = r.rotate()
    assert res["rotated"] is False
    assert res["endpoint"] is None
    assert res["reason"] == "No endpoints configured"


def test_rotate_single_endpoint_noop():
    r = VPNRotator(endpoints=["ep1"])
    res = r.rotate()
    assert res["rotated"] is True
    assert res["endpoint"] == "ep1"
    assert res["reason"] == "single_endpoint_noop"


def test_rotate_round_robin():
    r = VPNRotator(endpoints=["ep1", "ep2", "ep3"])
    first = r.rotate()
    assert first["endpoint"] == "ep1"
    assert first["next_index"] == 1
    second = r.rotate()
    assert second["endpoint"] == "ep2"
    third = r.rotate()
    assert third["endpoint"] == "ep3"
    # বাংলা: চতুর্থ রোটেশন আবার ep1-এ ফিরে আসবে
    fourth = r.rotate()
    assert fourth["endpoint"] == "ep1"


def test_current_returns_active_endpoint():
    r = VPNRotator(endpoints=["ep1", "ep2"])
    assert r.current() == "ep1"
    r.rotate()
    assert r.current() == "ep2"


def test_current_empty_returns_none():
    r = VPNRotator(endpoints=[])
    assert r.current() is None


def test_history_records_rotations():
    r = VPNRotator(endpoints=["ep1", "ep2"])
    r.rotate()
    r.rotate()
    events = [h["event"] for h in r.history]
    assert events.count("rotate") == 2


def test_endpoints_stripped_of_whitespace():
    r = VPNRotator(endpoints=["  ep1  ", "", "ep2"])
    assert r.endpoints == ["ep1", "ep2"]
