from __future__ import annotations

import unittest

from services.config_registry import safe_defaults, schema, validate_value


class ConfigRegistryTests(unittest.TestCase):
    def test_defaults_are_available_for_registered_keys(self) -> None:
        defaults = safe_defaults()
        self.assertEqual(defaults["runtime.max_concurrency"], 5)
        self.assertTrue(defaults["feature.cost_guard"])

    def test_public_schema_excludes_private_entries(self) -> None:
        public_keys = {item["key"] for item in schema(public_only=True)}
        self.assertIn("feature.cost_guard", public_keys)
        self.assertNotIn("runtime.max_concurrency", public_keys)

    def test_bounds_are_enforced(self) -> None:
        self.assertEqual(validate_value("runtime.max_concurrency", 10), 10)
        with self.assertRaises(ValueError):
            validate_value("runtime.max_concurrency", 0)
        with self.assertRaises(ValueError):
            validate_value("runtime.max_concurrency", 101)

    def test_unknown_keys_are_rejected(self) -> None:
        with self.assertRaises(KeyError):
            validate_value("unknown.setting", True)


if __name__ == "__main__":
    unittest.main()
