import pytest
import time
from tools.vpn_switcher import VPNRotator

def test_vpn_rotator_no_endpoints():
    rotator = VPNRotator()
    assert not rotator.status()["configured"]
    assert rotator.current() is None
    
    res = rotator.rotate()
    assert not res["rotated"]
    assert "No endpoints" in res["reason"]

def test_vpn_rotator_rotate():
    rotator = VPNRotator(endpoints=["proxy1", "proxy2"])
    assert rotator.status()["configured"]
    assert rotator.current() == "proxy1"
    
    # 1st rotation
    res = rotator.rotate()
    assert res["rotated"]
    assert res["endpoint"] == "proxy1"
    assert res["previous"] == "proxy2"
    assert res["next_index"] == 1
    
    # 2nd rotation
    res2 = rotator.rotate()
    assert res2["rotated"]
    assert res2["endpoint"] == "proxy2"
    assert res2["previous"] == "proxy1"
    assert res2["next_index"] == 0

def test_vpn_rotator_add_and_configure():
    rotator = VPNRotator()
    res = rotator.configure_endpoints(["p1", "p2"])
    assert res["count"] == 2
    
    # Add endpoint
    res_add = rotator.add_endpoint("p3")
    assert res_add["added"]
    assert res_add["count"] == 3
    
    # Status check
    status = rotator.status()
    assert status["count"] == 3
    assert status["history_count"] == 2 # configure and add
    
    # History since filter
    now = time.time()
    rotator.rotate()
    history = rotator.history_since(now - 1)
    assert len(history) >= 1
    assert history[-1]["event"] == "rotate"
