import asyncio
import uuid

from utils.uuid_gen import UUIDv7, generate_uuid7


class TestGenerateUuid7:
    def test_returns_uuid(self):
        value = generate_uuid7()
        assert isinstance(value, uuid.UUID)

    def test_unique_per_call(self):
        a = generate_uuid7()
        b = generate_uuid7()
        assert a != b


class TestUUIDv7Type:
    def test_process_bind_param_none(self):
        t = UUIDv7()
        assert t.process_bind_param(None, None) is None

    def test_process_bind_param_accepts_uuid(self):
        t = UUIDv7()
        original = uuid.uuid4()
        assert t.process_bind_param(original, None) == original

    def test_process_bind_param_converts_str(self):
        t = UUIDv7()
        raw = "12345678-1234-5678-1234-567812345678"
        result = t.process_bind_param(raw, None)
        assert isinstance(result, uuid.UUID)
        assert str(result) == raw

    def test_process_bind_param_invalid_str_raises(self):
        t = UUIDv7()
        try:
            t.process_bind_param("not-a-uuid", None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Silenced error: {e}")
        else:
            raise AssertionError("expected invalid uuid string to raise")

    def test_process_result_value_none(self):
        t = UUIDv7()
        assert t.process_result_value(None, None) is None

    def test_process_result_value_passthrough(self):
        t = UUIDv7()
        value = uuid.uuid4()
        assert t.process_result_value(value, None) == value

    def test_cache_ok(self):
        assert UUIDv7.cache_ok is True
