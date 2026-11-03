"""Tests for #2252 (MODULE_04 P-A) — browser session allowed_actions."""

from __future__ import annotations

import pytest

from core.browser_session_manager import BrowserSession


class TestAllowedActions:
    def test_default_allowed_actions_contains_navigate_screenshot_content_extract(self):
        session = BrowserSession(
            id="s1", owner_id="u1", context=None, page=None, created_at=0.0, last_used_at=0.0
        )
        assert "navigate" in session.allowed_actions
        assert "screenshot" in session.allowed_actions
        assert "content" in session.allowed_actions
        assert "extract" in session.allowed_actions

    def test_click_is_allowed(self):
        session = BrowserSession(
            id="s1", owner_id="u1", context=None, page=None, created_at=0.0, last_used_at=0.0
        )
        assert "click" in session.allowed_actions

    def test_fill_is_allowed(self):
        session = BrowserSession(
            id="s1", owner_id="u1", context=None, page=None, created_at=0.0, last_used_at=0.0
        )
        assert "fill" in session.allowed_actions

    def test_type_is_allowed(self):
        session = BrowserSession(
            id="s1", owner_id="u1", context=None, page=None, created_at=0.0, last_used_at=0.0
        )
        assert "type" in session.allowed_actions

    def test_total_action_count_is_seven(self):
        session = BrowserSession(
            id="s1", owner_id="u1", context=None, page=None, created_at=0.0, last_used_at=0.0
        )
        assert len(session.allowed_actions) == 7

    @pytest.mark.parametrize(
        "action", ["navigate", "screenshot", "content", "extract", "click", "fill", "type"]
    )
    def test_each_advertised_action_passes_allowlist_gate(self, action):
        session = BrowserSession(
            id="s1", owner_id="u1", context=None, page=None, created_at=0.0, last_used_at=0.0
        )
        assert action in session.allowed_actions

    def test_unknown_action_still_blocked(self):
        session = BrowserSession(
            id="s1", owner_id="u1", context=None, page=None, created_at=0.0, last_used_at=0.0
        )
        assert "delete" not in session.allowed_actions
        assert "inject" not in session.allowed_actions

    def test_custom_allowed_actions_override_still_works(self):
        session = BrowserSession(
            id="s1",
            owner_id="u1",
            context=None,
            page=None,
            created_at=0.0,
            last_used_at=0.0,
            allowed_actions=("navigate",),
        )
        assert session.allowed_actions == ("navigate",)
