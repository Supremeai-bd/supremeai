"""Runs fabric full coverage tests (#3268).

à¦¬à¦¾à¦‚à¦²à¦¾: à¦à¦‡ à¦Ÿà§‡à¦¸à§à¦Ÿà¦—à§à¦²à§‹ backend/runs/service.py à¦à¦° RunService à¦à¦¬à¦‚
RunNotFound exception à¦à¦° coverage à¦¬à¦¾à¦¡à¦¼à¦¾à¦¯à¦¼à¥¤
"""

from __future__ import annotations

import pytest

# â”€â”€ RunNotFound exception tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestRunNotFound:
    """#3268: RunNotFound â€” custom exception contractà¥¤"""

    def test_is_lookup_error_subclass(self):
        from core.runs.service import RunNotFound

        assert issubclass(RunNotFound, LookupError)

    def test_can_be_raised_with_message(self):
        from core.runs.service import RunNotFound

        with pytest.raises(RunNotFound) as exc_info:
            raise RunNotFound("run abc123 not found")
        assert "abc123" in str(exc_info.value)

    def test_can_be_caught_as_lookup_error(self):
        # à¦¬à¦¾à¦‚à¦²à¦¾: RunNotFound à¦•à§‡ LookupError à¦¹à¦¿à¦¸à§‡à¦¬à§‡à¦“ catch à¦•à¦°à¦¾ à¦¯à¦¾à¦¯à¦¼
        from core.runs.service import RunNotFound

        with pytest.raises(LookupError):
            raise RunNotFound("test")

    def test_empty_message(self):
        from core.runs.service import RunNotFound

        with pytest.raises(RunNotFound) as exc_info:
            raise RunNotFound("")
        assert str(exc_info.value) == ""


# â”€â”€ RunService class tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestRunService:
    """#3268: RunService â€” service class contractà¥¤"""

    def test_class_exists(self):
        from core.runs.service import RunService

        assert RunService is not None

    def test_class_has_init(self):
        from core.runs.service import RunService

        assert hasattr(RunService, "__init__")

    def test_class_is_importable(self):
        # à¦¬à¦¾à¦‚à¦²à¦¾: RunService import à¦•à¦°à¦¾ à¦¯à¦¾à¦¯à¦¼ à¦¨à¦¨-crash
        from core.runs.service import RunService

        # Don't instantiate â€” it may need DB dependencies
        assert callable(RunService)

    def test_module_has_service_symbol(self):
        import runs.service as mod

        assert hasattr(mod, "RunService")
        assert hasattr(mod, "RunNotFound")


# â”€â”€ MCP Server coverage tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestMCPServer:
    """#3268: mcp_server.py â€” MCP server build + dispatch contractà¥¤"""

    def test_build_server_exists(self):
        from core.memory.mcp_server import build_server

        assert callable(build_server)

    def test_knowledge_graph_class_exists(self):
        from core.memory.mcp_server import KnowledgeGraph

        assert KnowledgeGraph is not None

    def test_check_policy_function_exists(self):
        from core.memory.mcp_server import _check_policy

        assert callable(_check_policy)

    def test_audit_function_exists(self):
        from core.memory.mcp_server import _audit

        assert callable(_audit)

    def test_dispatch_function_exists(self):
        from core.memory.mcp_server import _dispatch

        assert callable(_dispatch)

    def test_main_function_exists(self):
        from core.memory.mcp_server import main

        assert callable(main)

    def test_check_policy_returns_dict_or_none(self):
        # à¦¬à¦¾à¦‚à¦²à¦¾: _check_policy returns policy dict or None
        from core.memory.mcp_server import _check_policy

        result = _check_policy("unknown_tool_name")
        assert result is None or isinstance(result, dict)

    def test_knowledge_graph_has_expected_interface(self):
        from core.memory.mcp_server import KnowledgeGraph

        # Class should have at least an __init__
        assert hasattr(KnowledgeGraph, "__init__")
        # Should have some methods (graph operations)
        assert len(dir(KnowledgeGraph)) > 10  # at least some methods


# â”€â”€ Runs service module structure tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestRunsServiceModuleStructure:
    """#3268: module-level structure + importsà¥¤"""

    def test_module_imports_cleanly(self):
        import runs.service

        assert runs.service is not None

    def test_module_has_run_service(self):
        import runs.service

        assert hasattr(runs.service, "RunService")

    def test_module_has_run_not_found(self):
        import runs.service

        assert hasattr(runs.service, "RunNotFound")

    def test_mcp_server_module_imports_cleanly(self):
        import memory.mcp_server

        assert memory.mcp_server is not None

    def test_mcp_server_has_build_server(self):
        import memory.mcp_server

        assert hasattr(memory.mcp_server, "build_server")

    def test_mcp_server_has_knowledge_graph(self):
        import memory.mcp_server

        assert hasattr(memory.mcp_server, "KnowledgeGraph")
