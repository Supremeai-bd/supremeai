"""Tests for the workflow structural validity guard.

The guard exists because GitHub enforces structural rules on workflow files that
PyYAML does not. On 2026-11-20 a 26th `workflow_dispatch` input (GitHub's limit
is 25) caused GitHub to reject the whole of `ops-maintenance.yml`; the run showed
zero jobs, so nothing pointed at the cause. These tests pin that rule and the
other structural checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

from workflow_validity_guard import MAX_DISPATCH_INPUTS, validate  # noqa: E402

MINIMAL = "on: push\njobs:\n  a:\n    runs-on: x\n    steps:\n      - run: e\n"


def _dispatch_inputs(count: int) -> str:
    inputs = "".join(f"      i{n}:\n        type: boolean\n" for n in range(count))
    return (
        "on:\n  workflow_dispatch:\n    inputs:\n"
        + inputs
        + "jobs:\n  a:\n    runs-on: x\n    steps:\n      - run: e\n"
    )


class TestDispatchInputLimit:
    """Rule 9: GitHub rejects the whole file above 25 dispatch inputs."""

    def test_limit_is_25(self):
        assert MAX_DISPATCH_INPUTS == 25

    def test_at_the_limit_is_accepted(self):
        assert validate("<at>", _dispatch_inputs(25)) == []

    def test_one_over_the_limit_is_rejected(self):
        problems = validate("<over>", _dispatch_inputs(26))
        assert len(problems) == 1
        assert "26 workflow_dispatch inputs" in problems[0]
        assert "limit 25" in problems[0]

    def test_far_over_the_limit_is_rejected(self):
        assert validate("<way-over>", _dispatch_inputs(40))

    def test_no_dispatch_trigger_is_fine(self):
        assert validate("<inline>", MINIMAL) == []


class TestStructuralRules:
    def test_minimal_workflow_is_clean(self):
        assert validate("<min>", MINIMAL) == []

    def test_missing_on_is_reported(self):
        text = "jobs:\n  a:\n    runs-on: x\n    steps:\n      - run: e\n"
        assert any("no `on:` trigger" in p for p in validate("<p>", text))

    def test_scalar_on_is_accepted(self):
        # `on: push` parses to {True: "push"}; presence must not be truthiness.
        assert validate("<scalar>", MINIMAL) == []

    def test_dangling_needs_is_reported(self):
        text = (
            "on: push\njobs:\n  a:\n    needs: ghost\n"
            "    runs-on: x\n    steps:\n      - run: e\n"
        )
        assert any("unknown job 'ghost'" in p for p in validate("<p>", text))

    def test_missing_runs_on_is_reported(self):
        text = "on: push\njobs:\n  a:\n    steps:\n      - run: e\n"
        assert any("no `runs-on`" in p for p in validate("<p>", text))

    def test_step_with_neither_uses_nor_run(self):
        text = "on: push\njobs:\n  a:\n    runs-on: x\n    steps:\n      - name: s\n"
        assert any("neither `uses` nor `run`" in p for p in validate("<p>", text))

    def test_step_with_both_uses_and_run(self):
        text = (
            "on: push\njobs:\n  a:\n    runs-on: x\n"
            "    steps:\n      - uses: a/b@v1\n        run: e\n"
        )
        assert any("both `uses` and `run`" in p for p in validate("<p>", text))

    def test_reusable_workflow_job_is_accepted(self):
        text = "on: push\njobs:\n  a:\n    uses: o/r/.github/workflows/w.yml@v1\n"
        assert validate("<reuse>", text) == []

    def test_invalid_permission_scope_is_reported(self):
        text = (
            "on: push\npermissions:\n  bogus: read\njobs:\n"
            "  a:\n    runs-on: x\n    steps:\n      - run: e\n"
        )
        assert any("unknown permission scope" in p for p in validate("<p>", text))

    def test_invalid_permission_level_is_reported(self):
        text = (
            "on: push\npermissions:\n  contents: admin\njobs:\n"
            "  a:\n    runs-on: x\n    steps:\n      - run: e\n"
        )
        assert any("invalid level" in p for p in validate("<p>", text))

    def test_unparseable_yaml_is_reported(self):
        problems = validate("<bad>", "on: [unclosed\n")
        assert len(problems) == 1
        assert "YAML does not parse" in problems[0]

    def test_non_mapping_document_is_reported(self):
        assert any("not a mapping" in p for p in validate("<list>", "- a\n- b\n"))


class TestRealRepository:
    """The guard must pass on every workflow actually committed in this repo."""

    def test_all_committed_workflows_are_structurally_valid(self):
        root = Path(__file__).resolve().parents[1]
        workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
        assert workflows, "no workflow files found"
        problems = []
        for path in workflows:
            problems.extend(validate(str(path), path.read_text(encoding="utf-8")))
        assert problems == []

    def test_dispatch_input_limit_is_respected_by_every_workflow(self):
        """The exact regression: no workflow may exceed GitHub's 25-input cap."""
        import yaml

        root = Path(__file__).resolve().parents[1]
        for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            triggers = doc.get("on", doc.get(True))
            if not isinstance(triggers, dict):
                continue
            dispatch = triggers.get("workflow_dispatch")
            if not isinstance(dispatch, dict):
                continue
            inputs = dispatch.get("inputs") or {}
            assert len(inputs) <= MAX_DISPATCH_INPUTS, (
                f"{path.name} defines {len(inputs)} workflow_dispatch inputs; "
                f"GitHub rejects the entire file above {MAX_DISPATCH_INPUTS}"
            )
