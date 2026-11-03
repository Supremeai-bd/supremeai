"""Tests for memory_consolidation_guard (Memory pillar)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.memory_consolidation_guard import (
    audit_memory,
    find_exact_duplicates,
    find_contradictions,
    find_near_duplicates,
    load_input,
)


def test_clean_memory() -> None:
    entries = [{"key": "a", "text": "hello"}, {"key": "b", "text": "world"}]
    assert audit_memory(entries)["ok"] is True


def test_exact_duplicate() -> None:
    entries = [{"key": "a", "text": "x"}, {"key": "a", "text": "x"}]
    assert find_exact_duplicates(entries)


def test_contradiction() -> None:
    entries = [{"key": "a", "text": "v1"}, {"key": "a", "text": "v2"}]
    assert find_contradictions(entries)


def test_near_duplicate() -> None:
    entries = [{"key": "a", "text": "same"}, {"key": "b", "text": "same"}]
    assert find_near_duplicates(entries)


def test_load_input(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"entries": [{"key": "a", "text": "t"}]}), encoding="utf-8")
    assert len(load_input(str(p))) == 1