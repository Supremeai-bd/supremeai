"""Tests for scripts/ci/generate_agents_md.py (SSOT -> AGENTS.md renderer).

AGENTS.md is a generated governance document: the drift gate fails when it is
hand-edited. These tests pin the generator contract so the renderer itself
cannot silently change how the constitution is rendered.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

_SPEC = importlib.util.spec_from_file_location(
    "generate_agents_md_under_test", Path("scripts/ci/generate_agents_md.py")
)
gen = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = gen
_SPEC.loader.exec_module(gen)

MINIMAL_RULES = {
    "constitution": {
        "name": "Test Constitution",
        "rules_version": "9.9",
        "philosophy_quote": "quote",
        "philosophy_line": "line",
        "operator_creed": ["never guess", "fail closed"],
    },
    "bootstrap": [],
    "gates": {"tier1": {"title": "Tier 1", "blocks_when": "bad syntax", "wired": True, "workflow": "ci.yml"}},
    "hard_rules": {"rule_1": "be safe", "rule_2": "stay atomic"},
    "freedoms": ["refactor freely"],
}


def test_render_is_deterministic_and_has_generated_header():
    a = gen.render(MINIMAL_RULES)
    b = gen.render(MINIMAL_RULES)
    assert a == b
    assert a.startswith("<!-- GENERATED FILE — DO NOT EDIT BY HAND -->")
    assert "rules_version: `9.9`" in a
    assert "be safe" in a and "never guess" in a


def test_render_covers_hard_rules_and_freedoms():
    text = gen.render(MINIMAL_RULES)
    assert "be safe" in text and "stay atomic" in text
    assert "refactor freely" in text
    # the registry pointer survives so humans know where to edit
    assert ".github/constitution/rules.yml" in text


def test_committee_rules_render_and_current_ssot_passes_check():
    """The committed SSOT must render byte-identical to the committed AGENTS.md."""
    rules = yaml.safe_load(gen.RULES_PATH.read_text(encoding="utf-8"))
    rendered = gen.render(rules)
    committed = gen.AGENTS_PATH.read_text(encoding="utf-8")
    assert rendered == committed, (
        "AGENTS.md is drifted from .github/constitution/rules.yml — "
        "run: python3 scripts/ci/generate_agents_md.py"
    )


def test_check_mode_exit_code(monkeypatch, tmp_path):
    rules = yaml.safe_load(gen.RULES_PATH.read_text(encoding="utf-8"))
    clean = tmp_path / "AGENTS.md"
    clean.write_text(gen.render(rules), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["generate_agents_md.py", "--check", "--out", str(clean)])
    assert gen.main() == 0  # clean render passes
    clean.write_text(gen.render(rules) + "\n<!-- drift -->", encoding="utf-8")
    assert gen.main() == 1  # drift detected
