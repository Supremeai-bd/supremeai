"""HeadlessAgentRegistry (tools/headless_agent_registry.py) এর ইউনিট টেস্ট।

বাংলা: get_headless_agent_configs()-এর লোকাল ফলব্যাক পাথ কভার করা হয়েছে
(ডেটাবেজ কানেকশন ব্যর্থ হলে ডিফল্ট এজেন্ট কনফিগ রিটার্ন করে)। settings মক করা হয়েছে।
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tools import headless_agent_registry


def test_get_configs_fallback_returns_dict():
    # বাংলা: DB কানেকশন None রিটার্ন করলে লোকাল ডিফল্ট কনফিগ ফেরত দেয়
    # _get_connection একটি লোকাল import, তাই সোর্স মডিউলে প্যাচ করা হয়েছে
    with (
        patch.object(headless_agent_registry, "settings", MagicMock()),
        patch("tools.mcp.mcp_supabase._get_connection", return_value=None),
    ):
        configs = headless_agent_registry.get_headless_agent_configs()
        assert isinstance(configs, dict)
        assert "gemini-cli" in configs
        assert "openhands" in configs


def test_get_configs_db_error_falls_back():
    # বাংলা: DB কোয়েরি এক্সেপশন দিলেও graceful ফলব্যাক
    with (
        patch.object(headless_agent_registry, "settings", MagicMock()),
        patch("tools.mcp.mcp_supabase._get_connection", side_effect=Exception("db down")),
    ):
        configs = headless_agent_registry.get_headless_agent_configs()
        assert "gemini-cli" in configs


def test_get_configs_has_required_keys():
    with (
        patch.object(headless_agent_registry, "settings", MagicMock()),
        patch("tools.mcp.mcp_supabase._get_connection", return_value=None),
    ):
        configs = headless_agent_registry.get_headless_agent_configs()
        for name, cfg in configs.items():
            assert "command" in cfg
            assert "args" in cfg
            assert "allowed_tools" in cfg
            assert "mcp_servers" in cfg
