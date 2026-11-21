"""Model Context Protocol (MCP) server tooling SSOT."""

import sys

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None  # type: ignore[assignment, misc]

__all__ = ["FastMCP"]

# Alias both import paths to THIS module object, mirroring the pattern
# `core.tools` itself uses (`sys.modules["tools"] = sys.modules[__name__]`).
#
# This package is importable two ways — the legacy bare `tools.mcp.*` path
# (via `core/` on sys.path, used by tests and headless_agent_registry) and the
# canonical `core.tools.mcp.*` path (imported BY these submodules themselves).
# Without the alias the two names resolve to different module objects; once
# `core.tools` is imported first, `import tools.mcp.mcp_neon as mn` breaks at
# the `import ... as` binding step because `core.tools.mcp` (the shadow
# instance) never receives the freshly-loaded submodule attribute.
sys.modules["core.tools.mcp"] = sys.modules[__name__]
sys.modules["tools.mcp"] = sys.modules[__name__]
