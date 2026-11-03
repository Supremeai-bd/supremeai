"""#1833 — advertised-vs-actual API contract tests.

বাংলা: public /docs পেজ আর কখনো অস্বলুত endpoint দেখাবে না, আর
health-aggregation তার docstring-অনুযায়ী /admin-api/health-aggregation-এই
মাউন্ট থাকবে (double prefix নিষিদ্ধ)।
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_PAGES = REPO_ROOT / "frontend" / "src" / "pages" / "PublicPages.tsx"
ROUTERS = REPO_ROOT / "backend" / "api" / "routers.py"
HEALTH_AGG = REPO_ROOT / "backend" / "api" / "routes" / "health_aggregation.py"


class TestDocsPageContract:
    def test_fabricated_chat_completions_row_removed(self):
        text = FRONTEND_PAGES.read_text(encoding="utf-8")
        assert "chat/completions" not in text, (
            "public /docs must not advertise endpoints that do not exist"
        )

    def test_real_chat_entrypoints_documented(self):
        text = FRONTEND_PAGES.read_text(encoding="utf-8")
        assert "/api/v1/stream/chat" in text, "real SSE chat entrypoint must be listed"
        assert "/api/chat/orchestrate" in text, "real orchestration entrypoint must be listed"


class TestHealthAggregationMount:
    def test_no_double_prefix_in_registry(self):
        import re

        text = ROUTERS.read_text(encoding="utf-8")
        block_match = re.search(
            r'\{\s*(?:#[^}]*\n\s*)*"path":\s*"api\.routes\.health_aggregation".*?\}',
            text,
            re.DOTALL,
        )
        assert block_match, "health_aggregation registry entry not found"
        block = block_match.group(0)
        assert '"prefix": ""' in block, (
            "health_aggregation must mount prefix-less (its own /admin-api prefix applies)"
        )

    def test_live_path_matches_docstring_and_frontend(self):
        router_text = HEALTH_AGG.read_text(encoding="utf-8")
        assert 'prefix="/admin-api"' in router_text
        monitor_path = (
            REPO_ROOT
            / "frontend"
            / "src"
            / "components"
            / "admin"
            / "infra"
            / "ServiceHealthMonitor.tsx"
        )
        if monitor_path.exists():
            frontend = monitor_path.read_text(encoding="utf-8")
            assert "/admin-api/health-aggregation" in frontend
            assert "/api/admin-api" not in frontend, (
                "frontend must not call the double-prefixed path"
            )
