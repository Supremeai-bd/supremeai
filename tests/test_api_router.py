import os

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest
from unittest.mock import MagicMock


class TestApiRouter:
    def test_register_and_supports(self):
        from brain.api_router import ApiRouter
        router = ApiRouter()
        handler = MagicMock(return_value={"ok": True})
        router.register("echo", handler)
        assert router.supports("echo") is True
        assert router.supports("missing") is False

    def test_capabilities_returns_signatures(self):
        from brain.api_router import ApiRouter
        router = ApiRouter()
        fn = lambda x: x
        router.register("transform", fn)
        caps = router.capabilities()
        assert "transform" in caps

    def test_dispatch_calls_handler(self):
        from brain.api_router import ApiRouter
        router = ApiRouter()
        handler = MagicMock(return_value={"result": 42})
        router.register("compute", handler)
        out = router.dispatch("compute", {"n": 7})
        assert out == {"result": 42}
        handler.assert_called_once_with({"n": 7})

    def test_dispatch_missing_capability_raises(self):
        from brain.api_router import ApiRouter
        router = ApiRouter()
        with pytest.raises(KeyError):
            router.dispatch("unknown", {})

    def test_dispatch_handler_exception_returns_error(self):
        from brain.api_router import ApiRouter
        router = ApiRouter()
        router.register("fail", MagicMock(side_effect=RuntimeError("boom")))
        out = router.dispatch("fail", {})
        assert out["success"] is False
        assert "boom" in out["error"]

    def test_register_lambda_inspect_fails_stores_none_signature(self):
        from brain.api_router import ApiRouter
        router = ApiRouter()
        broken = "not callable"
        router.register("bad", broken)
        assert "bad" in router._signatures
