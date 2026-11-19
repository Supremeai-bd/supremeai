"""Fail-closed tests for the landing-decision composition rule.

The authority (`tiny_brain_pr_guard.py`) decides; the advisor
(`ai_pr_evaluator.py`) may only *hold*, never widen. These tests pin that
asymmetry so a future "helpful" upgrade path cannot be added silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import landing_decision_compose as compose_mod


@pytest.mark.parametrize(
    ("advisor", "expected"),
    [
        ("HOLD_AND_FIX", ("OWNER_REVIEW", "advisor_hold")),
        ("CLOSE", ("OWNER_REVIEW", "advisor_close")),
        ("hold_and_fix", ("OWNER_REVIEW", "advisor_hold")),
    ],
)
def test_advisor_can_hold_an_auto_merge(advisor, expected):
    assert compose_mod.compose("AUTO_MERGE", "clean", advisor) == expected


@pytest.mark.parametrize("advisor", ["AUTO_MERGE", "PENDING", None, "", "WHATEVER"])
def test_advisor_never_upgrades_and_noops_on_unknown(advisor):
    assert compose_mod.compose("AUTO_MERGE", "clean", advisor) == ("AUTO_MERGE", "clean")


@pytest.mark.parametrize(
    ("decision", "expected"),
    [("OWNER_REVIEW", "OWNER_REVIEW"), ("BLOCKED", "BLOCKED"), ("", ""),
     ("pending", "PENDING")],  # decisions are normalised to upper case
)
def test_non_auto_merge_decisions_are_never_touched(decision, expected):
    assert compose_mod.compose(decision, "protected_paths_changed", "AUTO_MERGE") == (
        expected,
        "protected_paths_changed",
    )


@pytest.mark.parametrize("decision", ["BLOCKED", "OWNER_REVIEW"])
def test_advisor_cannot_upgrade_a_hold_or_a_block(decision):
    out = compose_mod.compose(decision, "ci_not_success:fast-gate", "AUTO_MERGE")
    assert out[0] == decision


def test_parse_verdict_reads_json_after_log_noise():
    stdout = "\n".join(
        [
            "evaluating PR #42 ...",
            "::warning::llm unavailable, deterministic fallback",
            json.dumps({"pr": 42, "verdict": "HOLD_AND_FIX", "value_reasons": []}),
        ]
    )
    assert compose_mod.parse_verdict(stdout) == "HOLD_AND_FIX"


def test_parse_verdict_ignores_malformed_and_non_verdict_json():
    stdout = "\n".join(
        [
            "{not json}",
            json.dumps({"pr": 42}),
            '{"verdict": ',
            json.dumps(["AUTO_MERGE"]),
        ]
    )
    assert compose_mod.parse_verdict(stdout) is None


def test_parse_verdict_last_object_wins():
    stdout = "\n".join(
        [json.dumps({"verdict": "PENDING"}), json.dumps({"verdict": "CLOSE"})]
    )
    assert compose_mod.parse_verdict(stdout) == "CLOSE"


def test_empty_stdout_is_a_noop(tmp_path, capsys):
    rc = compose_mod.main(["--decision", "AUTO_MERGE", "--reason", "clean",
                           "--advisor-stdout", str(tmp_path / "missing.txt")])
    assert rc == 0
    assert capsys.readouterr().out == "decision=AUTO_MERGE\nreason=clean\n"


def test_cli_applies_downgrade(tmp_path, capsys):
    evidence = tmp_path / "advisor.out"
    evidence.write_text(json.dumps({"verdict": "CLOSE"}), encoding="utf-8")
    rc = compose_mod.main(["--decision", "AUTO_MERGE", "--reason", "clean",
                           "--advisor-stdout", str(evidence)])
    assert rc == 0
    assert capsys.readouterr().out == "decision=OWNER_REVIEW\nreason=advisor_close\n"
