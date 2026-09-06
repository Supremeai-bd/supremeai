import json
import tempfile
import unittest
from pathlib import Path

from scripts.ci.generate_module_capability_matrix import build


class TestModuleCapabilityMatrix(unittest.TestCase):
    def test_matrix_is_structured_and_classified(self):
        matrix = build()
        self.assertEqual(matrix["schema_version"], "1.0")
        self.assertGreater(matrix["module_count"], 0)
        self.assertTrue(all("classification" in item for item in matrix["modules"]))

    def test_matrix_paths_are_repository_relative(self):
        matrix = build()
        self.assertTrue(all(not Path(item["path"]).is_absolute() for item in matrix["modules"]))


if __name__ == "__main__":
    unittest.main()
