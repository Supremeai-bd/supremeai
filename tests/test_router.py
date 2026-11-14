"""Tests for the autonomy router compatibility shim (#107, #108)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "agents"))

from router import DynamicRouter, MODEL_CHAINS


def test_bengali_selects_kimi():
    r = DynamicRouter()
    m = r.select("bengali")
    assert "kimi" in m.lower() or "moonshot" in m.lower()


def test_code_selects_deepseek():
    r = DynamicRouter()
    m = r.select("code")
    assert "deepseek" in m.lower()


def test_local_selects_gemini():
    r = DynamicRouter()
    m = r.select("local")
    assert "gemini" in m.lower()


def test_deterministic():
    r = DynamicRouter()
    assert r.select("code") == r.select("code")


def test_route_alias():
    r = DynamicRouter()
    assert r.route("bengali") == r.select("bengali")


def test_call_alias():
    r = DynamicRouter()
    assert r("code") == r.select("code")
