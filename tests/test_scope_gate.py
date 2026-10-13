"""Step-security.1 regression guards (#109) — claim-time customer-isolation Scope Gate.

Fail-closed decision matrix: customer/tenant demand × supremeai_internal (Layer 1)
task = deterministic refusal + evidence. combined_ecosystem = allow with explicit
marker + internal restricted list. Taxonomy SSOT = lint_plans.TARGET_SCOPES (reused,
not redefined). Wiring: continuous_agent_loop claim path (preflight).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agents.scope_gate import (  # noqa: E402
    CUSTOMER_DEMAND_SCOPES,
    DEMAND_SCOPE_ENV,
    audit_log,
    evaluate_claim,
    resolve_demand_scope,
    resolve_task_scope,
    scope_gate_preflight,
)
from scripts.governance.lint_plans import TARGET_SCOPES  # noqa: E402


class CustomerIsolationTests(unittest.TestCase):
    """মূল চুক্তি: customer/tenant demand × Layer 1 task = fail-closed refusal।"""

    def test_customer_demand_internal_task_refused(self):
        d = evaluate_claim("customer_facing", "supremeai_internal")
        self.assertFalse(d["allowed"])
        self.assertIn("customer-isolation-violation", d["reason"])

    def test_tenant_demand_internal_task_refused(self):
        for demand in ("customer_tenant", "tenant"):
            d = evaluate_claim(demand, "supremeai_internal")
            self.assertFalse(d["allowed"], f"{demand} লেনে ভেদ হয়ে যাচ্ছে")
            self.assertEqual(d["demand_scope"], "customer_facing")  # alias normalize

    def test_customer_demand_customer_task_allowed(self):
        d = evaluate_claim("customer_facing", "customer_facing")
        self.assertTrue(d["allowed"])

    def test_internal_demand_internal_task_allowed_default_unchanged(self):
        # বাংলা: বর্তমান monorepo বাস্তবতা — demand ঘোষণা ছাড়া আচরণ অপরিবর্তিত।
        d = evaluate_claim("supremeai_internal", "supremeai_internal")
        self.assertTrue(d["allowed"])


class FailClosedTests(unittest.TestCase):
    """অজানা/অবৈধ মান = refusal — কখনো চুপচাপ allow নয় (U6)।"""

    def test_invalid_task_scope_refused(self):
        d = evaluate_claim("supremeai_internal", "galaxy_wide")
        self.assertFalse(d["allowed"])
        self.assertIn("invalid-task-scope", d["reason"])

    def test_invalid_demand_scope_refused_everything(self):
        d = evaluate_claim("random_lane", "customer_facing")
        self.assertFalse(d["allowed"])
        self.assertIn("invalid-demand-scope", d["reason"])

    def test_empty_scopes_refused(self):
        self.assertFalse(evaluate_claim("", "")["allowed"])

    def test_ssot_not_shadowed(self):
        # বাংলা: gate নিজের কপি বানায়নি — lint_plans-এর SSOT-ই একমাত্র ভোকাবুলারি।
        for scope in TARGET_SCOPES:
            self.assertIn(scope, evaluate_claim("supremeai_internal", scope)["task_scope"] or scope)


class CombinedEcosystemTests(unittest.TestCase):
    """combined = allow + explicit marker + internal-layer restricted list।"""

    def test_combined_allowed_with_marker(self):
        d = evaluate_claim("customer_facing", "combined_ecosystem")
        self.assertTrue(d["allowed"])
        self.assertEqual(d["marker"], "combined_ecosystem:internal-touch-restricted")

    def test_restricted_list_intersects_declared_with_internal_prefixes(self):
        files = ["backend/core/config.py", "client/app.tsx", "scripts/ci/merge_gate.py"]
        d = evaluate_claim("customer_facing", "combined_ecosystem", files)
        self.assertEqual(d["restricted_internal_files"],
                         ["backend/core/config.py", "scripts/ci/merge_gate.py"])

    def test_restricted_list_empty_when_no_internal_files_declared(self):
        d = evaluate_claim("customer_facing", "combined_ecosystem", ["client/app.tsx"])
        self.assertEqual(d["restricted_internal_files"], [])

    def test_internal_demand_combined_also_marked(self):
        d = evaluate_claim("supremeai_internal", "combined_ecosystem")
        self.assertTrue(d["allowed"])
        self.assertIsNotNone(d["marker"])


class ResolutionPrecedenceTests(unittest.TestCase):
    def test_explicit_overrides_env(self):
        old = __import__("os").environ.get(DEMAND_SCOPE_ENV)
        try:
            __import__("os").environ[DEMAND_SCOPE_ENV] = "customer_facing"
            self.assertEqual(resolve_demand_scope("supremeai_internal"), "supremeai_internal")
            self.assertEqual(resolve_demand_scope(), "customer_facing")
        finally:
            if old is None:
                __import__("os").environ.pop(DEMAND_SCOPE_ENV, None)
            else:
                __import__("os").environ[DEMAND_SCOPE_ENV] = old

    def test_task_scope_label_over_body_over_default(self):
        self.assertEqual(resolve_task_scope(["scope:combined_ecosystem"], "target_scope: customer_facing"),
                         "combined_ecosystem")
        self.assertEqual(resolve_task_scope([], "target_scope: customer_facing"), "customer_facing")
        self.assertEqual(resolve_task_scope([], ""), "supremeai_internal")  # presumed Layer 1


class EvidenceAndAuditTests(unittest.TestCase):
    def test_refusal_carries_fingerprint_evidence(self):
        d = evaluate_claim("customer_facing", "supremeai_internal", ["backend/core/db.py"])
        self.assertTrue(d["fingerprint"])
        self.assertEqual(len(d["fingerprint"]), 12)

    def test_fingerprint_deterministic(self):
        a = evaluate_claim("customer_facing", "supremeai_internal", ["a.py", "b.py"])
        b = evaluate_claim("customer_facing", "supremeai_internal", ["b.py", "a.py"])
        self.assertEqual(a["fingerprint"], b["fingerprint"])  # order-insensitive

    def test_audit_log_is_valid_deterministic_json(self):
        d = evaluate_claim("customer_facing", "supremeai_internal")
        line = audit_log(d)
        self.assertEqual(json.loads(line), d)  # round-trip
        self.assertEqual(audit_log(d), line)  # deterministic

    def test_preflight_fail_closed_on_fetch_failure(self):
        # gh ব্যর্থ → body শূন্য → task presumed Layer 1 → customer demand-এ refusal।
        import os
        old = os.environ.get(DEMAND_SCOPE_ENV)
        try:
            os.environ[DEMAND_SCOPE_ENV] = "customer_facing"
            d = scope_gate_preflight(999999999, {"labels": []}, None)
            self.assertFalse(d["allowed"])
        finally:
            if old is None:
                os.environ.pop(DEMAND_SCOPE_ENV, None)
            else:
                os.environ[DEMAND_SCOPE_ENV] = old


if __name__ == "__main__":
    unittest.main()
