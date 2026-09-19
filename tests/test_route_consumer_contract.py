"""CI contract test — route → frontend-consumer inventory (issue #480 step 5).

Gates (mirror of the generated-artifact contract tests in tests/, e.g.
test_module_capability_matrix.py):

(a) every scanned backend route carries an explicit disposition — classified
    (user-facing / admin-only / internal / deprecated) or intentionally
    API-only via the allowlist (scripts/audit/api_only_routes.txt);
(b) the committed inventory (docs/generated/route_consumer_inventory.json)
    matches a fresh in-process regeneration — same drift-gate pattern as the
    capability matrix;
(c) no NEW orphan appears: a route classified ``orphaned`` in the fresh scan
    that is neither recorded in the committed inventory nor allowlisted fails
    the gate. Pre-existing orphaned families recorded in the committed
    baseline never fail (that debt is tracked for issue #480 steps 3-4).

Pure stdlib on both sides — the generator never imports the app.

Note on granularity: the allowlist is family-level, so a NEW endpoint under an
already-allowlisted family inherits that family's pending "intentionally
API-only" disposition instead of failing; the drift gate (b) still forces the
regenerated inventory (showing the new endpoint) to be reviewed and committed.
"""

import json
import unittest

from scripts.audit.generate_route_consumer_inventory import (
    ALLOWLIST_FILE,
    CLASSIFICATIONS,
    OUT_JSON,
    build_inventory,
    classify,
    detect_new_orphans,
    load_allowlist,
    route_family,
)

_SYNTHETIC_ORPHAN = {
    "method": "POST",
    "path": "/api/v1/contract-test-probe/unwired",
    "declared": "/api/v1/contract-test-probe/unwired",
    "router_file": "backend/api/routes/__contract_test_probe__.py",
    "module": "api.routes.__contract_test_probe__",
    "registry_prefix": "",
    "mounted": True,
    "is_admin": False,
    "operation": "unwired_probe",
    "deprecated": False,
    "frontend_consumers": [],
}


class RouteConsumerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = build_inventory()
        cls.allowlist = load_allowlist()

    # -- allowlist hygiene ---------------------------------------------------

    def test_allowlist_file_exists_with_owner_prune_header(self) -> None:
        self.assertTrue(ALLOWLIST_FILE.is_file(), f"{ALLOWLIST_FILE} missing")
        header = ALLOWLIST_FILE.read_text(encoding="utf-8").lower()
        self.assertIn("prune", header, "allowlist header must tell owners to prune")

    def test_allowlist_entries_are_normalized_families(self) -> None:
        for family in self.allowlist:
            self.assertTrue(family.startswith("/"), family)
            self.assertNotIn("{", family, "families are param-normalized")

    # -- gate (a): explicit disposition for every route ----------------------

    def test_every_route_has_an_explicit_disposition(self) -> None:
        routes = self.inventory["routes"]
        self.assertGreater(len(routes), 0, "no backend routes scanned")
        for route in routes:
            self.assertIn(
                route["classification"],
                CLASSIFICATIONS,
                f"{route['method']} {route['path']} has unknown classification",
            )
            self.assertNotEqual(
                route["classification"],
                "orphaned",
                "NEW orphaned route — wire a frontend consumer, classify it "
                "(admin/internal/deprecated), or add its family to "
                "scripts/audit/api_only_routes.txt: "
                f"{route['method']} {route['path']} ({route['router_file']})",
            )

    def test_totals_match_recomputed_counts(self) -> None:
        totals = self.inventory["totals"]
        routes = self.inventory["routes"]
        self.assertEqual(totals["backend_routes"], len(routes))
        recomputed = {c: 0 for c in CLASSIFICATIONS}
        for route in routes:
            recomputed[route["classification"]] += 1
        self.assertEqual(totals["by_classification"], recomputed)
        self.assertEqual(
            totals["routes_with_frontend_consumer"],
            sum(1 for route in routes if route["frontend_consumers"]),
        )
        self.assertEqual(totals["orphan_routes"], recomputed["orphaned"])

    # -- gate (b): committed artifact matches a fresh regeneration -----------

    def test_committed_inventory_matches_fresh_regeneration(self) -> None:
        self.assertTrue(
            OUT_JSON.is_file(),
            "committed inventory missing — run "
            "python scripts/audit/generate_route_consumer_inventory.py "
            "and commit docs/generated/route_consumer_inventory.*",
        )
        committed = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        self.assertEqual(
            committed,
            self.inventory,
            "docs/generated/route_consumer_inventory.json is stale — regenerate "
            "with `python scripts/audit/generate_route_consumer_inventory.py` "
            "and commit the diff",
        )

    # -- gate (c): newly orphaned routes fail --------------------------------

    def test_no_new_orphans_relative_to_committed_baseline(self) -> None:
        committed = (
            json.loads(OUT_JSON.read_text(encoding="utf-8"))
            if OUT_JSON.is_file()
            else None
        )
        new_orphans = detect_new_orphans(self.inventory, committed, self.allowlist)
        self.assertEqual(
            new_orphans,
            [],
            "NEW orphaned route(s) detected (no frontend consumer, no "
            "classification, not allowlisted): "
            + "; ".join(f"{r['method']} {r['path']}" for r in new_orphans[:10]),
        )

    def test_gate_detects_a_synthetic_new_orphan(self) -> None:
        """Self-test: the step-5 gate must flag a genuinely new orphan."""
        probe = dict(_SYNTHETIC_ORPHAN)
        probe["classification"] = classify(probe, self.allowlist)
        self.assertEqual(probe["classification"], "orphaned")
        fresh = {"routes": [dict(_SYNTHETIC_ORPHAN, classification="orphaned")]}
        # Not in the committed baseline, not allowlisted → detected.
        self.assertEqual(
            detect_new_orphans(fresh, self.inventory, self.allowlist),
            [fresh["routes"][0]],
        )
        # Recorded in the committed baseline → tolerated (step 3-4 debt).
        self.assertEqual(detect_new_orphans(fresh, fresh, self.allowlist), [])
        # Family allowlisted → intentionally API-only, not an orphan failure.
        family = route_family(_SYNTHETIC_ORPHAN["path"])
        self.assertEqual(detect_new_orphans(fresh, self.inventory, [family]), [])

    def test_allowlisted_route_with_consumer_is_user_facing(self) -> None:
        """Wiring landing over an allowlisted family re-classifies user-facing."""
        route = dict(_SYNTHETIC_ORPHAN)
        route["path"] = "/api/v1/contract-test-probe/wired"
        route["frontend_consumers"] = ["frontend/src/services/probe.ts"]
        self.assertEqual(classify(route, self.allowlist), "user-facing")


if __name__ == "__main__":
    unittest.main()
