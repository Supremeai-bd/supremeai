from unittest.mock import MagicMock

from core.rules_mutator import RulesMutator


def test_is_ip_blocked_when_redis_not_configured(monkeypatch):
    rm = RulesMutator()
    from core import services

    monkeypatch.setattr(services, "redis_queue", MagicMock(configured=False), raising=False)
    assert rm.is_ip_blocked("1.2.3.4") is False


def test_block_and_release_ip(monkeypatch):
    rm = RulesMutator()
    redis = MagicMock()
    redis.configured = True
    storage = {}

    def get(key):
        return storage.get(key)

    def set(key, value, ex=None):
        storage[key] = value
        return True

    redis.get = MagicMock(side_effect=get)
    redis.set = MagicMock(side_effect=set)

    from core import services

    monkeypatch.setattr(services, "redis_queue", redis, raising=False)

    assert rm.block_ip("9.9.9.9", reason="r") is True
    assert redis.set.called

    assert rm.is_ip_blocked("9.9.9.9") is True

    assert rm.release_ip("9.9.9.9") is True
