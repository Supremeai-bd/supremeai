from __future__ import annotations

import os
import time
from typing import Any, Dict, List


def get_mcp_servers() -> Dict[str, Any]:
    settings: Dict[str, Any] = {
        "github": {
            "command": "uvx",
            "args": ["mcp-server-github"],
            "env": {"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "")},
            "allowed_paths": ["/api/v1/gateway"],
            "allowed_tools": ["search_repositories", "get_file_contents", "create_issue"],
        },
        "slack": {
            "command": "uvx",
            "args": ["mcp-server-slack"],
            "env": {"SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", "")},
            "allowed_paths": ["/api/v1/gateway"],
            "allowed_tools": ["send_message", "list_channels"],
        },
        "filesystem": {
            "command": "uvx",
            "args": ["mcp-server-filesystem", os.getenv("MCP_ALLOWED_DIR", os.getcwd())],
            "allowed_paths": ["/api/v1/gateway"],
            "allowed_tools": ["read_file", "write_file", "list_directory"],
        },
    }
    return settings


class MCPAllowlist:
    @staticmethod
    def validate_server(name: str) -> Dict[str, Any]:
        servers = get_mcp_servers()
        server = servers.get(name)
        if not server:
            return {"allowed": False, "reason": "unknown mcp server"}
        return {"allowed": True, "server": name, "tools": server.get("allowed_tools", [])}

    @staticmethod
    def allowed_tools(server_name: str, requested: List[str]) -> Dict[str, Any]:
        info = MCPAllowlist.validate_server(server_name)
        if not info["allowed"]:
            return {"allowed": False, "denied": requested}
        allowed = list(info.get("tools", []))
        denied = [tool for tool in requested if tool not in allowed]
        return {"allowed": not bool(denied), "allowed_tools": allowed, "denied": denied}
