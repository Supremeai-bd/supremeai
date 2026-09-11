import json
import tempfile
import unittest
from pathlib import Path

from scripts.ci.generate_module_capability_matrix import build


class TestModuleCapabilityMatrix(unittest.TestCase):
    def test_matrix_is_structured_and_classified(self):
        matrix = build()
        self.assertEqual(matrix["schema_version"], "2.0")
        self.assertEqual(matrix["inventory_type"], "source_file_capability")
        self.assertGreater(matrix["source_file_count"], 0)
        self.assertEqual(matrix["source_file_count"], len(matrix["modules"]))
        self.assertEqual(matrix["functional_module_inventory"], "MODULES_LIST.md")
        self.assertIsInstance(matrix["functional_module_count"], int)
        self.assertTrue(all("classification" in item for item in matrix["modules"]))

    def test_matrix_paths_are_repository_relative(self):
        matrix = build()
        self.assertTrue(all(not Path(item["path"]).is_absolute() for item in matrix["modules"]))


if __name__ == "__main__":
    unittest.main()
