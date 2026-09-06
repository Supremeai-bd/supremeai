import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "ci"))
from route_graph_query import RouteGraph


class TestRouteGraph(unittest.TestCase):
    def setUp(self):
        self.graph = RouteGraph({
            "nodes": [
                {"id": "contract:1", "kind": "contract", "label": "openapi"},
                {"id": "route:1", "kind": "route", "label": "GET /items"},
                {"id": "capability:1", "kind": "capability", "label": "items"},
            ],
            "edges": [
                {"source": "contract:1", "relation": "defines", "target": "route:1"},
                {"source": "route:1", "relation": "exposes", "target": "capability:1"},
            ],
        })

    def test_find_and_neighbors_are_stable(self):
        self.assertEqual(self.graph.find(kind="route")[0]["label"], "GET /items")
        self.assertEqual(self.graph.neighbors("contract:1")[0]["id"], "route:1")
        self.assertEqual(self.graph.neighbors("route:1", direction="incoming")[0]["id"], "contract:1")

    def test_traverse_is_bounded_and_reports_depth(self):
        result = self.graph.traverse("contract:1", max_depth=1, max_nodes=2)
        self.assertEqual([(node["id"], node["depth"]) for node in result], [("contract:1", 0), ("route:1", 1)])

    def test_invalid_direction_and_limits_fail(self):
        with self.assertRaises(ValueError):
            self.graph.neighbors("contract:1", direction="sideways")
        with self.assertRaises(ValueError):
            self.graph.traverse("contract:1", max_nodes=0)


if __name__ == "__main__":
    unittest.main()
