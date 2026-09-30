"""Topological Sequence Audit tests — 3-Tier Verification Contract (#2682).

Tier 1: rules.yml schema consistency (validate_rules_schema on the REAL file)
Tier 2: pytest suite (this file — audit_topological_sequence + helpers)
Tier 3: loop simulation — agent CANNOT claim a UI/API task while a lower-layer
        task is still open (topological_task_gate).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.audit_suite import (
    audit_topological_sequence,
    classify_layer,
    classify_layers,
    has_reflection_evidence,
    load_rules,
    parse_layer_from_body,
    scan_open_issue_layers,
    topological_task_gate,
    validate_rules_schema,
)

REFLECTION_BODY = """## Summary
Frontend-only polish.

## Reflection Evidence
**why:** the underlying tools/worker capability already exists (backend/tools/render worker is live).
**alternatives_rejected:** (1) adding a new backend worker — rejected as duplication; (2) API change — rejected, contract is stable.
"""

NO_EVIDENCE_BODY = """## Summary
UI tweak without any reflection.
"""


class TestClassifyLayer(unittest.TestCase):
    def test_layer1_schemas_and_contracts(self):
        # বাংলা: স্কিমা/কনট্র্যাক্ট ফাইল লেয়ার ১
        self.assertEqual(classify_layer("packages/shared-types/src/index.ts"), 1)
        self.assertEqual(classify_layer("backend/schemas/user.py"), 1)
        self.assertEqual(classify_layer("backend/models/task.py"), 1)

    def test_layer2_tools_workers(self):
        # বাংলা: টুল/ওয়ার্কার লেয়ার ২ — বাধ্যতামূলক ভিত্তি
        self.assertEqual(classify_layer("backend/tools/render.py"), 2)
        self.assertEqual(classify_layer("backend/workers/queue_worker.py"), 2)
        self.assertEqual(classify_layer("scripts/ci/audit_suite.py"), 2)

    def test_layer3_core_engine(self):
        # বাংলা: কোর ইঞ্জিন/স্টেট মেশিন লেয়ার ৩
        self.assertEqual(classify_layer("backend/core/app_builder.py"), 3)
        self.assertEqual(classify_layer("backend/services/gateway_center.py"), 3)
        self.assertEqual(classify_layer("packages/core-infrastructure/src/circuit.py"), 3)

    def test_layer4_api_routes(self):
        # বাংলা: API এন্ডপয়েন্ট লেয়ার ৪
        self.assertEqual(classify_layer("backend/api/server.py"), 4)
        self.assertEqual(classify_layer("backend/ws/stream.py"), 4)

    def test_layer5_frontend(self):
        # বাংলা: ফ্রন্টএন্ড/UI লেয়ার ৫
        self.assertEqual(classify_layer("frontend/src/App.tsx"), 5)
        self.assertEqual(classify_layer("frontend/src/pages/user/SkillCatalog.tsx"), 5)

    def test_unknown_paths_return_none(self):
        # বাংলা: ডকুমেন্টেশন/অজানা পাথ অডিটের বাইরে
        self.assertIsNone(classify_layer("README.md"))
        self.assertIsNone(classify_layer("docs/guide.md"))

    def test_layer_normalization(self):
        # বাংলা: leading ./ ও ব্যাকস্ল্যাশ নরমালাইজ হয়
        self.assertEqual(classify_layer("./frontend/src/main.tsx"), 5)
        self.assertEqual(classify_layer("frontend\\src\\main.tsx"), 5)

    def test_classify_layers_groups_by_layer(self):
        grouped = classify_layers(["backend/api/x.py", "backend/tools/y.py", "frontend/src/a.tsx"])
        self.assertEqual(set(grouped), {2, 4, 5})


class TestReflectionEvidence(unittest.TestCase):
    def test_full_evidence_passes(self):
        # বাংলা: why + alternatives_rejected — সম্পূর্ণ প্রতিফলন
        self.assertTrue(has_reflection_evidence(REFLECTION_BODY))

    def test_missing_header_fails(self):
        # বাংলা: হেডারই নেই → প্রতিফলন নেই
        self.assertFalse(has_reflection_evidence("why we did it, alternatives rejected: a, b"))

    def test_missing_alternatives_fails(self):
        # বাংলা: why আছে কিন্তু rejected বিকল্প নেই → অসম্পূর্ণ
        body = "## Reflection Evidence\nwhy: existing tool covers it.\n"
        self.assertFalse(has_reflection_evidence(body))

    def test_empty_body_fails(self):
        self.assertFalse(has_reflection_evidence(None))
        self.assertFalse(has_reflection_evidence(""))


class TestAuditTopologicalSequence(unittest.TestCase):
    def test_low_layer_only_always_passes(self):
        # বাংলা: নিচের লেয়ারের কাজ — ভিত্তি নির্মাণ, সবসময় পাস
        res = audit_topological_sequence(["backend/tools/new_worker.py", "backend/schemas/w.yaml"], None)
        self.assertTrue(res.passed)
        self.assertEqual(res.max_layer, 2)

    def test_upper_layer_with_grounding_passes(self):
        # বাংলা: L4 API + L2 worker grounding — capability-before-construction সন্তুষ্ট
        res = audit_topological_sequence(
            ["backend/api/deploy.py", "backend/tools/deploy_worker.py"], None,
        )
        self.assertTrue(res.passed)
        self.assertIsNotNone(res.grounded_low_layer_file)

    def test_ui_only_without_evidence_blocks(self):
        # বাংলা (মূল ইনভেরিয়েন্ট): শুধু UI বদলাল, ভিত্তি/প্রতিফলন কিছুই নেই → BLOCK
        res = audit_topological_sequence(
            ["frontend/src/pages/user/SkillCatalog.tsx"], NO_EVIDENCE_BODY,
        )
        self.assertFalse(res.passed)
        self.assertIn("TOPOLOGICAL VIOLATION", res.reason)

    def test_api_only_without_evidence_blocks(self):
        # বাংলা: শুধু API-ও একইভাবে ব্লক হবে
        res = audit_topological_sequence(["backend/api/server.py"], NO_EVIDENCE_BODY)
        self.assertFalse(res.passed)

    def test_ui_only_with_reflection_evidence_passes(self):
        # বাংলা: প্রতিফলনের প্রমাণ থাকলে শুধু-UI PR গ্রহণযোগ্য
        res = audit_topological_sequence(
            ["frontend/src/components/export/ExportMenu.tsx"], REFLECTION_BODY,
        )
        self.assertTrue(res.passed)
        self.assertTrue(res.reflection_evidence)

    def test_docs_only_not_applicable(self):
        # বাংলা: ডকস-ওনলি PR — অডিট প্রাসঙ্গিক নয়, পাস
        res = audit_topological_sequence(["README.md", "docs/x.md"], None)
        self.assertTrue(res.passed)
        self.assertIsNone(res.max_layer)

    def test_empty_file_list(self):
        res = audit_topological_sequence([], None)
        self.assertTrue(res.passed)


class TestRulesSchemaTier1(unittest.TestCase):
    def test_real_rules_yml_is_consistent(self):
        # Tier 1 (Verification Contract): আসল rules.yml স্কিমা-বৈধ থাকতে হবে
        rules = load_rules()
        errors = validate_rules_schema(rules)
        self.assertEqual(errors, [], f"real rules.yml must be schema-consistent: {errors}")

    def test_missing_required_key_detected(self):
        bad = {"architecture": {"rule_099": {"title": "x", "severity": "BLOCK"}}}
        errors = validate_rules_schema(bad)
        self.assertTrue(any("description" in e for e in errors))
        self.assertTrue(any("category" in e for e in errors))

    def test_invalid_severity_detected(self):
        bad = {"architecture": {"rule_001": {
            "title": "t", "description": "d", "severity": "FATAL", "category": "architecture",
        }}}
        self.assertTrue(any("invalid severity" in e for e in validate_rules_schema(bad)))

    def test_category_must_be_nonempty_string(self):
        # বাংলা: canonical ফাইল সংক্ষিপ্ত slug ('arch') ব্যবহার করে — তাই সমতা নয়,
        # কেবল non-empty string যাচাই (খালি/অস্ট্রিং হলে এরর)
        bad = {"security": {"rule_001": {
            "title": "t", "description": "d", "severity": "BLOCK", "category": "",
        }}}
        self.assertTrue(any("category" in e for e in validate_rules_schema(bad)))
        good = {"security": {"rule_001": {
            "title": "t", "description": "d", "severity": "BLOCK", "category": "arch",
        }}}
        self.assertEqual(validate_rules_schema(good), [])

    def test_gate_requires_workflow(self):
        bad = {"gates": {"my_gate": {"title": "t", "blocks_when": "b", "wired": True}}}
        self.assertTrue(any("workflow" in e for e in validate_rules_schema(bad)))

    def test_gate_workflow_must_be_yml(self):
        bad = {"gates": {"my_gate": {"title": "t", "blocks_when": "b", "wired": True, "workflow": "pr"}}}
        self.assertTrue(any(".yml" in e for e in validate_rules_schema(bad)))


class TestTopologicalTaskGateTier3(unittest.TestCase):
    """Tier 3: লুপ সিমুলেশন — নিচের লেয়ার খোলা থাকলে ওপরের লেয়ার ক্লেইম অসম্ভব।"""

    def test_ui_task_blocked_while_tools_open(self):
        # বাংলা: টুল/ওয়ার্কার (L2) টাস্ক খোলা — UI (L5) ক্লেইম নিষিদ্ধ
        open_layers = {2700: 2, 2701: 5}
        allowed, reason = topological_task_gate(2701, 5, open_layers)
        self.assertFalse(allowed)
        self.assertIn("#2700", reason)

    def test_ui_task_allowed_when_foundation_clear(self):
        # বাংলা: নিচের কোনো লেয়ার টাস্ক খোলা নেই — ভিত্তি পরিষ্কার, ক্লেইম অনুমোদিত
        allowed, _ = topological_task_gate(2701, 5, {2702: 5})
        self.assertTrue(allowed)

    def test_unlayered_task_always_allowed(self):
        # বাংলা: লেয়ার ঘোষণা নেই (পুরানো/বাহ্যিক ইস্যু) — গেট বাধা দেয় না
        allowed, _ = topological_task_gate(1234, None, {2700: 2})
        self.assertTrue(allowed)

    def test_foundation_task_always_allowed(self):
        # বাংলা: ফাউন্ডেশন (L1/L2) নিজে কখনোই ব্লক হয় না
        allowed, _ = topological_task_gate(2700, 2, {2701: 5, 2702: 4})
        self.assertTrue(allowed)

    def test_self_issue_not_blocking_itself(self):
        # বাংলা: নিজের ঘোষিত লেয়ার নিজেকে ব্লক করবে না
        allowed, _ = topological_task_gate(2701, 4, {2701: 4})
        self.assertTrue(allowed)

    def test_parse_layer_from_template_body(self):
        # বাংলা: নতুন টেমপ্লেটের 'Layer: 5 (Frontend...)' আউটপুট পার্স হয়
        self.assertEqual(parse_layer_from_body("### Layer\nLayer: 5 (Frontend & Client UI)"), 5)
        self.assertEqual(parse_layer_from_body("**Layer:** 2"), 2)
        self.assertIsNone(parse_layer_from_body("no layer here"))

    def test_scan_open_issue_layers(self):
        issues = [
            {"number": 2700, "body": "Layer: 2 (Tools / Workers)"},
            {"number": 2701, "body": "Layer: 5"},
            {"number": 2702, "body": "no layer"},
        ]
        self.assertEqual(scan_open_issue_layers(issues), {2700: 2, 2701: 5})


if __name__ == "__main__":
    unittest.main()
