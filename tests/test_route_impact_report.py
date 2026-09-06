import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "ci"))
from route_graph_query import RouteGraph
from route_impact_report import build_impact_report


class TestRouteImpactReport(unittest.TestCase):
    def setUp(self):
        self.graph = RouteGraph({
            "nodes": [
                {"id": "route:a", "kind": "route", "label": "GET /a"},
                {"id": "cap:a", "kind": "capability", "label": "a"},
                {"id": "policy:a", "kind": "policy", "label": "auth"},
            ],
            "edges": [
                {"source": "route:a", "relation": "exposes", "target": "cap:a"},
                {"source": "cap:a", "relation": "governed_by", "target": "policy:a"},
            ],
        })

    def test_report_is_deterministic_and_bounded(self):
        report = build_impact_report(self.graph, ["route:a"], max_depth=1, max_nodes=10)
        self.assertEqual(report["impact_count"], 2)
        self.assertEqual([node["id"] for node in report["impacted_nodes"]], ["route:a", "cap:a"])
        self.assertEqual(report["missing_roots"], [])

    def test_missing_roots_are_explicit(self):
        report = build_impact_report(self.graph, ["missing"])
        self.assertEqual(report["impact_count"], 0)
        self.assertEqual(report["missing_roots"], ["missing"])

    def test_empty_roots_fail(self):
        with self.assertRaises(ValueError):
            build_impact_report(self.graph, [])


if __name__ == "__main__":
    unittest.main()
