"""Roadmap v2.0 Phase 3 step-4 regression guards (#4145).

The learning loop (#4054) WRITES knowledge/skills + regression_guards YAMLs
with inject_rule "on_task_assignment_if_similar" — the readers must surface
them for compose_agent_context injection (fail-honest, task-matched).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.learning.skill_template_writer import (
    read_regression_guards,
    read_skill_templates,
)

SKILL_YAML = """\
skill_id: "skill_backend_bug_use_pytest"
task_type: "backend_bug"
decision_type: "test_first"
outcome: "success"
confidence: 0.8
sample_count: 3
inject_rule: "on_task_assignment_if_similar"
"""
GUARD_YAML = """\
guard_id: "guard_backend_bug_swallow"
task_type: "backend_bug"
decision_type: "swallow_errors"
failure_count: 4
inject_rule: "on_task_assignment_if_similar"
block_rule: "warn_on_match"
"""


class LearnedKnowledgeReaderTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "knowledge" / "skills").mkdir(parents=True)
        (self.root / "knowledge" / "regression_guards").mkdir(parents=True)

    def test_missing_dir_is_empty_not_crash(self):
        self.assertEqual(read_skill_templates(repo_root=self.root / "nope"), [])

    def test_task_match_filters(self):
        (self.root / "knowledge" / "skills" / "s1.yaml").write_text(SKILL_YAML)
        (self.root / "knowledge" / "skills" / "s2.yaml").write_text(
            SKILL_YAML.replace("backend_bug", "frontend_bug")
        )
        hits = read_skill_templates("backend_bug", repo_root=self.root)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["task_type"], "backend_bug")
        self.assertEqual(hits[0]["_source_file"], "s1.yaml")
        # bidirectional substring match: broader query also hits
        self.assertEqual(len(read_skill_templates("bug", repo_root=self.root)), 2)

    def test_non_injectable_templates_excluded(self):
        (self.root / "knowledge" / "skills" / "s1.yaml").write_text(
            SKILL_YAML.replace('inject_rule: "on_task_assignment_if_similar"',
                               'inject_rule: "manual_only"')
        )
        self.assertEqual(read_skill_templates("backend_bug", repo_root=self.root), [])

    def test_malformed_yaml_skipped_fail_honest(self):
        (self.root / "knowledge" / "skills" / "bad.yaml").write_text(":::: not yaml [")
        (self.root / "knowledge" / "skills" / "ok.yaml").write_text(SKILL_YAML)
        hits = read_skill_templates("backend_bug", repo_root=self.root)
        self.assertEqual([h["_source_file"] for h in hits], ["ok.yaml"])

    def test_regression_guards_read(self):
        (self.root / "knowledge" / "regression_guards" / "g1.yaml").write_text(GUARD_YAML)
        hits = read_regression_guards("backend_bug", repo_root=self.root)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["block_rule"], "warn_on_match")


if __name__ == "__main__":
    unittest.main()
