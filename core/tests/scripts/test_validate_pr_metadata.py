"""#2158 — validate_pr_metadata.py contract tests.

বাংলা: PR #2156-তে bot wrapper ভুলে ফাইলের *ঠিকানা* title/body হিসেবে পাঠিয়েছিল
(`/tmp/wire_title.txt` literal)। এই টেস্টগুলো সেই exact failure class — এবং
Rule #16 conventional-title + gate-এর exactly-one-ref contract — সব lock করে,
যাতে যেকোনো bot wrapper pre-POST এ ধরতে পারে।

The script is loaded via importlib from the repo root (no package import),
so these tests run without the heavy backend import chain.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "agents" / "validate_pr_metadata.py"

_spec = importlib.util.spec_from_file_location("validate_pr_metadata", SCRIPT)
vpm = importlib.util.module_from_spec(_spec)
sys.modules["validate_pr_metadata"] = vpm
_spec.loader.exec_module(vpm)


GOOD_TITLE = "fix(agents): bot PR metadata pre-create validator (#2158)"
GOOD_BODY = (
    "## What\n\nAdds scripts/agents/validate_pr_metadata.py so bot wrappers can "
    "assert PR metadata before POSTing.\n\n## How tested\n\nUnit tests.\n\nRefs #2158"
)


class TestPathGarbageClass:
    """The literal #2156 failure: paths passed as title AND body."""

    def test_literal_2156_evidence_is_blocked(self):
        errors, _ = vpm.validate("/tmp/wire_title.txt", "/tmp/wire_body.md")
        joined = "\n".join(errors)
        assert "title looks like a filesystem path" in joined
        assert "body looks like a filesystem path" in joined

    def test_path_in_title_only_is_blocked(self):
        errors, _ = vpm.validate("/tmp/wire_title.txt", GOOD_BODY)
        assert any("title looks like a filesystem path" in e for e in errors)

    def test_repo_relative_path_in_body_is_blocked(self):
        errors, _ = vpm.validate(GOOD_TITLE, "docs/ops/pr_body.md")
        assert any("body looks like a filesystem path" in e for e in errors)

    def test_absolute_path_without_known_ext_is_blocked(self):
        errors, _ = vpm.validate(GOOD_TITLE, "/home/z/work/agent_api")
        assert any("body looks like a filesystem path" in e for e in errors)

    def test_prose_with_extension_word_passes_path_check(self):
        # Real prose mentioning extensions must not trip the path heuristic.
        errors, _ = vpm.validate(GOOD_TITLE, GOOD_BODY + " (we keep .md and .py files honest)")
        assert not any("filesystem path" in e for e in errors)


class TestRule16ConventionalTitle:
    def test_non_conventional_title_is_blocked(self):
        errors, _ = vpm.validate("wip stuff", GOOD_BODY)
        assert any("not conventional" in e for e in errors)

    def test_conventional_with_scope_passes(self):
        errors, warnings = vpm.validate(GOOD_TITLE, GOOD_BODY)
        assert not any("not conventional" in e for e in errors)

    def test_conventional_without_scope_passes(self):
        errors, _ = vpm.validate("chore: bump deps", GOOD_BODY)
        assert not any("not conventional" in e for e in errors)

    def test_missing_issue_pointer_warns_not_blocks(self):
        _, warnings = vpm.validate("fix(agents): no pointer here", GOOD_BODY)
        assert any("no trailing '(#N)'" in w for w in warnings)


class TestGateContract:
    def test_zero_keyword_refs_warns(self):
        body = GOOD_BODY.replace("Refs #2158", "linked: #2158")  # plain mention
        _, warnings = vpm.validate(GOOD_TITLE, body)
        assert any("no keyword-prefixed issue ref" in w for w in warnings)

    def test_two_keyword_refs_warn(self):
        body = GOOD_BODY + "\n\nFixes #2109"
        _, warnings = vpm.validate(GOOD_TITLE, body)
        assert any("2 keyword-prefixed issue refs" in w for w in warnings)

    def test_exactly_one_ref_is_clean(self):
        errors, warnings = vpm.validate(GOOD_TITLE, GOOD_BODY)
        assert not any("keyword-prefixed" in w for w in warnings)


class TestStubBodies:
    def test_empty_body_blocked(self):
        errors, _ = vpm.validate(GOOD_TITLE, "")
        assert any("body is empty" in e for e in errors)

    def test_tiny_body_blocked(self):
        errors, _ = vpm.validate(GOOD_TITLE, "see title")
        assert any("Rule #17" in e for e in errors)

    def test_empty_title_blocked(self):
        errors, _ = vpm.validate("", GOOD_BODY)
        assert any("title is empty" in e for e in errors)


class TestStrictAndCli:
    def test_strict_promotes_warnings(self):
        title_no_pointer = "fix(agents): no pointer here"
        errors, warnings = vpm.validate(title_no_pointer, GOOD_BODY, strict=True)
        assert warnings == []  # all promoted
        assert any("(#N)" in e for e in errors)

    def test_clean_metadata_has_no_errors(self):
        errors, warnings = vpm.validate(GOOD_TITLE, GOOD_BODY)
        assert errors == []
        assert warnings == []

    def test_cli_json_output_ok(self, capsys):
        sys.argv = [
            "validate_pr_metadata.py",
            "--title",
            GOOD_TITLE,
            "--body",
            GOOD_BODY,
            "--format",
            "json",
        ]
        try:
            rc = vpm.main()
        finally:
            sys.argv = ["validate_pr_metadata.py"]
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["ok"] is True

    def test_cli_json_output_path_garbage_exit_1(self, capsys):
        sys.argv = [
            "validate_pr_metadata.py",
            "--title",
            "/tmp/wire_title.txt",
            "--body",
            GOOD_BODY,
            "--format",
            "json",
        ]
        try:
            rc = vpm.main()
        finally:
            sys.argv = ["validate_pr_metadata.py"]
        assert rc == 1
        out = json.loads(capsys.readouterr().out)
        assert out["ok"] is False
        assert any("filesystem path" in e for e in out["errors"])
