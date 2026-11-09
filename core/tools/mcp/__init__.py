"""Model Context Protocol (MCP) server tooling SSOT."""

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None  # type: ignore[assignment, misc]

__all__ = ["FastMCP"]
