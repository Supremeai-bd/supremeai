import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/ci/generate_route_graph.py"
spec = importlib.util.spec_from_file_location("route_graph", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestRouteGraph(unittest.TestCase):
    def setUp(self):
        self.inventory = {
            "source": "backend/openapi.json",
            "source_sha256": "abc123",
            "routes": [
                {"method": "GET", "path": "/agents", "operation_id": "list_agents", "tags": ["agents"], "auth": {"required": True}, "owner": "unassigned"},
                {"method": "POST", "path": "/agents", "operation_id": "create_agent", "tags": ["agents"], "auth": {"required": True}, "owner": "unassigned"},
            ],
        }

    def test_graph_has_stable_unique_nodes_and_edges(self):
        first = module.build_graph(self.inventory)
        second = module.build_graph(self.inventory)
        self.assertEqual(first, second)
        self.assertEqual(first["node_count"], len(first["nodes"]))
        self.assertEqual(first["edge_count"], len(first["edges"]))
        self.assertEqual(len({node["id"] for node in first["nodes"]}), first["node_count"])
        self.assertEqual(len({json.dumps(edge, sort_keys=True) for edge in first["edges"]}), first["edge_count"])

    def test_authenticated_routes_require_control(self):
        graph = module.build_graph(self.inventory)
        controls = [edge for edge in graph["edges"] if edge["relation"] == "requires"]
        self.assertEqual(len(controls), 2)
        self.assertEqual(graph["source_sha256"], "abc123")


if __name__ == "__main__":
    unittest.main()
