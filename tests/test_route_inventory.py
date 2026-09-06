import unittest

from scripts.ci.generate_route_inventory import build_inventory


class RouteInventoryTests(unittest.TestCase):
    def test_extracts_routes_and_security(self) -> None:
        inventory = build_inventory(
            {
                "security": [{"BearerAuth": []}],
                "paths": {
                    "/health": {"get": {"operationId": "health_check", "tags": ["health"]}},
                    "/agents": {"post": {"operationId": "create_agent", "security": [{"OAuth2": []}]}},
                },
            },
            source="fixture.json",
        )
        self.assertEqual(inventory["route_count"], 2)
        self.assertEqual(inventory["routes"][0]["operation_id"], "create_agent")
        self.assertEqual(inventory["routes"][0]["auth"], {"required": True, "schemes": ["OAuth2"]})
        self.assertEqual(inventory["routes"][1]["auth"]["schemes"], ["BearerAuth"])

    def test_ignores_openapi_metadata_keys(self) -> None:
        inventory = build_inventory({"paths": {"/x": {"parameters": [], "get": {}}}})
        self.assertEqual(inventory["route_count"], 1)
        self.assertEqual(inventory["routes"][0]["method"], "GET")


if __name__ == "__main__":
    unittest.main()
