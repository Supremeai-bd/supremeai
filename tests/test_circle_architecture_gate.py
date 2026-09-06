import unittest
from pathlib import Path

from scripts.ci.circle_architecture_gate import violations


class CircleArchitectureGateTests(unittest.TestCase):
    def test_current_code_has_no_forbidden_circle_imports(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(violations(root), [])


if __name__ == "__main__":
    unittest.main()
