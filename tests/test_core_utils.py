import pytest

from core.feedback_loop import FeedbackLoop


@pytest.fixture
def loop():
    return FeedbackLoop()


def test_initial_metrics(loop):
    m = loop.metrics()
    assert m["edits"] == 0
    assert m["accepts"] == 0
    assert m["rejects"] == 0
    assert m["errors_reported"] == 0


def test_record_edit_increments_edits_and_returns_event(loop):
    event = loop.record_edit("/src/main.py", "added foo")
    assert event["type"] == "edit"
    assert event["file"] == "/src/main.py"
    assert event["diff"] == "added foo"
    assert "timestamp" in event
    m = loop.metrics()
    assert m["edits"] == 1


def test_record_accept_increments_accepts(loop):
    event = loop.record_suggestion_feedback(accepted=True)
    assert event["type"] == "suggestion_feedback"
    assert event["accepted"] is True
    m = loop.metrics()
    assert m["accepts"] == 1


def test_record_reject_increments_rejects(loop):
    event = loop.record_suggestion_feedback(accepted=False)
    assert event["accepted"] is False
    m = loop.metrics()
    assert m["rejects"] == 1


def test_record_error_report(loop):
    event = loop.record_error_report(ValueError("bad"), {"trace": "xyz"})
    assert event["type"] == "error"
    assert event["message"] == "bad"
    assert event["context"] == {"trace": "xyz"}
    m = loop.metrics()
    assert m["errors_reported"] == 1


def test_event_counting(loop):
    loop.record_edit("a", "d1")
    loop.record_edit("b", "d2")
    loop.record_suggestion_feedback(True)
    loop.record_suggestion_feedback(False)
    loop.record_error_report(RuntimeError("oops"), {})
    assert len(loop.events()) == 5
    assert len(loop.events(event_type="edit")) == 2
    assert len(loop.events(event_type="suggestion_feedback")) == 2
    assert len(loop.events(event_type="error")) == 1
    assert len(loop.events(event_type="missing")) == 0


def test_context_optional(loop):
    event = loop.record_suggestion_feedback(accepted=True, context=None)
    assert event["context"] == {}


def test_empty_text_returns_english(loop):
    from core.language_router import LanguageRouter
    r = LanguageRouter()
    assert r.detect("") == "english"
    assert r.detect("   ") == "english"


@pytest.mark.parametrize("text,expected", [
    ("Hello", "english"),
    ("বাংলা", "bengali"),
    ("你好", "chinese"),
    ("こんにちは", "japanese"),
    ("مرحبا", "arabic"),
    ("नमस्ते", "hindi"),
])
def test_language_detection_coverage(text, expected):
    from core.language_router import LanguageRouter
    r = LanguageRouter()
    assert r.detect(text) == expected


def test_route_provider_mapping():
    from core.language_router import LanguageRouter
    r = LanguageRouter()
    assert r.route("你好")["provider"] == "openrouter"
    assert r.route("বাংলা")["provider"] == "deepseek"
    assert r.route("مرحبا")["provider"] == "groq"


def test_get_mcp_servers_has_required_keys():
    from core.mcp_allowlist import get_mcp_servers
    servers = get_mcp_servers()
    assert isinstance(servers, dict)
    assert len(servers) >= 1
    for name, cfg in servers.items():
        assert "command" in cfg
        assert "allowed_tools" in cfg
        assert "allowed_paths" in cfg


def test_mcp_validate_denied_server():
    from core.mcp_allowlist import MCPAllowlist
    result = MCPAllowlist.validate_server("nonexistent")
    assert result["allowed"] is False


def test_mcp_allowed_tools_partially_denied():
    from core.mcp_allowlist import MCPAllowlist
    result = MCPAllowlist.allowed_tools("github", ["search_repositories", "banned_tool"])
    assert result["allowed"] is False
    assert "banned_tool" in result["denied"]
    assert result["allowed_tools"] == ["search_repositories", "get_file_contents", "create_issue"]


def test_circuit_breaker_initial_state():
    from core.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(name="test")
    assert cb.state == "CLOSED"
    assert cb.allow_request() is True


def test_circuit_breaker_opens_after_threshold():
    from core.circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(name="test", failure_threshold=2)
    assert cb.state == "CLOSED"
    cb.mark_failure()
    assert cb.state == "CLOSED"
    cb.mark_failure()
    assert cb.state == "OPEN"
    assert cb.allow_request() is False


def test_circuit_breaker_recovers():
    from core.circuit_breaker import CircuitBreaker
    import time
    cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
    cb.mark_failure()
    assert cb.state == "OPEN"
    time.sleep(0.15)
    assert cb.allow_request() is True


def test_rbac_has_permission():
    from core.rbac import RoleBasedAccessControl
    rb = RoleBasedAccessControl()
    assert rb.has_permission("admin", "admin") is True
    assert rb.has_permission("viewer", "write") is False


def test_rbac_require_denied():
    from core.rbac import RoleBasedAccessControl, UserContext
    rb = RoleBasedAccessControl()
    ctx = UserContext(user_id="1", role="viewer")
    result = rb.require(ctx, "write")
    assert result["allowed"] is False
    assert result["reason"] == "Permission denied"
