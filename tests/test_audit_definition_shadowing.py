import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "audit_definition_shadowing.py"

from scripts.ci.audit_definition_shadowing import (
    aggregate,
    audit_file,
    compare_against_baseline,
    load_baseline,
    write_baseline,
)


def _write(tmp: Path, name: str, source: str) -> Path:
    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


class DetectionTests(unittest.TestCase):
    def test_detects_duplicate_module_def(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(
                Path(tmp),
                "mod.py",
                "def run():\n    return 1\n\n\ndef run():\n    return 2\n",
            )
            findings = audit_file(path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["kind"], "shadowed_def")
            self.assertEqual(findings[0]["name"], "run")
            self.assertEqual(findings[0]["line"], 5)
            self.assertEqual(findings[0]["first_line"], 1)

    def test_detects_duplicate_class_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = "class Worker:\n    def tick(self):\n        return 1\n\n    def tick(self):\n        return 2\n"
            path = _write(Path(tmp), "worker.py", source)
            findings = audit_file(path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["kind"], "shadowed_method")
            self.assertEqual(findings[0]["name"], "tick")

    def test_detects_shadowed_module_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = "class Job:\n    pass\n\n\nclass Job:\n    pass\n"
            path = _write(Path(tmp), "jobs.py", source)
            findings = audit_file(path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["kind"], "shadowed_class")

    def test_detects_duplicate_dict_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = 'TIMEOUTS = {\n    "connect": 5,\n    "read": 10,\n    "connect": 30,\n}\n'
            path = _write(Path(tmp), "timeouts.py", source)
            findings = audit_file(path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["kind"], "shadowed_dict_key")
            self.assertIn("connect", str(findings[0]["name"]))

    def test_parse_error_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp), "broken.py", "def broken(:\n    pass\n")
            findings = audit_file(path)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["kind"], "parse_error")


class IntentionalPatternTests(unittest.TestCase):
    def test_property_setter_pair_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = (
                "class C:\n"
                "    @property\n"
                "    def size(self):\n"
                "        return self._size\n"
                "\n"
                "    @size.setter\n"
                "    def size(self, value):\n"
                "        self._size = value\n"
                "\n"
                "    @size.deleter\n"
                "    def size(self):\n"
                "        del self._size\n"
            )
            path = _write(Path(tmp), "prop.py", source)
            self.assertEqual(audit_file(path), [])

    def test_overload_stubs_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = (
                "from typing import overload\n"
                "\n"
                "\n"
                "@overload\n"
                "def parse(value: str) -> str: ...\n"
                "\n"
                "\n"
                "@overload\n"
                "def parse(value: bytes) -> bytes: ...\n"
                "\n"
                "\n"
                "def parse(value):\n"
                "    return value\n"
            )
            path = _write(Path(tmp), "parse.py", source)
            self.assertEqual(audit_file(path), [])

    def test_singledispatch_register_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = (
                "from functools import singledispatch\n"
                "\n"
                "\n"
                "@singledispatch\n"
                "def encode(value):\n"
                "    return str(value)\n"
                "\n"
                "\n"
                "@encode.register(str)\n"
                "def encode(value):\n"
                "    return value\n"
            )
            path = _write(Path(tmp), "encode.py", source)
            self.assertEqual(audit_file(path), [])


class BaselineGateTests(unittest.TestCase):
    def test_gate_fails_on_new_violation(self):
        current = {"backend/new.py": {("shadowed_def", "run"): 1}}
        baseline: dict = {}
        violations, _ = compare_against_baseline(current, baseline)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["note"], "NEW")

    def test_gate_fails_on_count_increase(self):
        current = {"backend/a.py": {("shadowed_def", "main"): 3}}
        baseline = {"backend/a.py": {("shadowed_def", "main"): 2}}
        violations, _ = compare_against_baseline(current, baseline)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["note"], "COUNT_INCREASED")

    def test_gate_allows_covered_findings(self):
        current = {"backend/a.py": {("shadowed_def", "main"): 2}}
        baseline = {"backend/a.py": {("shadowed_def", "main"): 2}}
        violations, improvements = compare_against_baseline(current, baseline)
        self.assertEqual(violations, [])
        self.assertEqual(improvements, [])

    def test_gate_allows_improvement_with_note(self):
        current = {"backend/a.py": {("shadowed_def", "main"): 1}}
        baseline = {"backend/a.py": {("shadowed_def", "main"): 2}}
        violations, improvements = compare_against_baseline(current, baseline)
        self.assertEqual(violations, [])
        self.assertTrue(
            any("resolved" in note or "->" in note for note in improvements)
        )

    def test_baseline_round_trip(self):
        findings = [
            {
                "file": "a.py",
                "line": 5,
                "kind": "shadowed_def",
                "name": "run",
                "first_line": 1,
            },
            {
                "file": "a.py",
                "line": 9,
                "kind": "shadowed_def",
                "name": "run",
                "first_line": 1,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path = Path(tmp) / "baseline.json"
            write_baseline(findings, baseline_path)
            loaded = load_baseline(baseline_path)
            self.assertEqual(loaded, {"a.py": {("shadowed_def", "run"): 2}})

    def test_aggregate_counts_per_file(self):
        findings = [
            {"file": "a.py", "kind": "shadowed_def", "name": "run"},
            {"file": "a.py", "kind": "shadowed_def", "name": "run"},
            {"file": "b.py", "kind": "shadowed_method", "name": "tick"},
        ]
        current = aggregate(findings)
        self.assertEqual(current["a.py"][("shadowed_def", "run")], 2)
        self.assertEqual(current["b.py"][("shadowed_method", "tick")], 1)


class CliIntegrationTests(unittest.TestCase):
    def test_report_only_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output",
                    str(Path(tmp) / "report.json"),
                    str(tmp),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(tmp) / "report.json").read_text())
            self.assertEqual(report["status"], "report-only")

    def test_gate_exits_one_on_new_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = "def hello():\n    return 1\n\n\ndef hello():\n    return 2\n"
            _write(Path(tmp), "probe.py", source)
            baseline_path = Path(tmp) / "baseline.json"
            baseline_path.write_text(
                json.dumps({"schema_version": 1, "entries": {}}), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output",
                    str(Path(tmp) / "report.json"),
                    "--baseline",
                    str(baseline_path),
                    str(tmp),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 1)
            report = json.loads((Path(tmp) / "report.json").read_text())
            self.assertEqual(report["status"], "fail")
            self.assertEqual(len(report["new_violations"]), 1)

    def test_gate_exits_zero_when_baseline_covers(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = "def hello():\n    return 1\n\n\ndef hello():\n    return 2\n"
            probe = _write(Path(tmp), "probe.py", source)
            findings = audit_file(probe)
            baseline_path = Path(tmp) / "baseline.json"
            write_baseline(findings, baseline_path)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output",
                    str(Path(tmp) / "report.json"),
                    "--baseline",
                    str(baseline_path),
                    str(tmp),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
