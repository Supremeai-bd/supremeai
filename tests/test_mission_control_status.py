"""Tests for mission_control_status (OS pillar)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.mission_control_status import aggregate, render_markdown, load_input


def test_green() -> None:
    r = aggregate([{"name": "a", "ok": True}, {"name": "b", "ok": True}])
    assert r["status"] == "GREEN" and r["ok"] is True


def test_red() -> None:
    r = aggregate([{"name": "a", "ok": False}])
    assert r["status"] == "RED" and r["failed"] == ["a"]


def test_empty_unknown() -> None:
    assert aggregate([])["status"] == "UNKNOWN"


def test_markdown() -> None:
    assert "GREEN" in render_markdown(aggregate([{"name": "a", "ok": True}]))


def test_load_input(tmp_path: Path) -> None:
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"gates": [{"name": "a", "ok": True}]}), encoding="utf-8")
    assert len(load_input(str(p))) == 1