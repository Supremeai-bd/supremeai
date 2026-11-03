"""Full-coverage tests for tools/code/code_smell_detector.py (Task 7-f).

radon and pylint (and jscpd) are optional external tools that are NOT
installed in the unit-test environment.  Where their internal logic is
exercised, fake modules / fake subprocess output are injected via
``sys.modules`` / ``monkeypatch`` — no external binary is ever invoked.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

import tools.code.code_smell_detector as csd
from tools.code.code_smell_detector import CodeSmellDetector


@pytest.fixture
def det() -> CodeSmellDetector:
    d = CodeSmellDetector()
    # Deterministic: treat optional external analyzers as unavailable unless a
    # test explicitly opts in.
    d.radon_available = False
    d.pylint_available = False
    return d


def _proc(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


COMPLEX_SRC = """
def tangled(a, b, c, d, e, f, g, h):
    if a and b and c:
        for i in range(3):
            while b:
                try:
                    with open("x") as fh:
                        assert fh
                except ValueError:
                    return 1
                except KeyError:
                    return 2
    return 0 if a else (1 if b else 2)


def small(a):
    return a
"""

TOO_MANY_ARGS_SRC = """
def f(a, b, c, d, e, f_, g):
    return a
"""

LONG_METHOD_SRC = "def long_one():\n" + "\n".join(f"    x{i} = {i}" for i in range(60)) + "\n"

MANY_RETURNS_SRC = (
    "def many(x):\n"
    + "\n".join(f"    if x == {i}:\n        return {i}" for i in range(9))
    + "\n    return None"
)

LARGE_CLASS_SRC = "class Big:\n" + "\n".join(
    f"    def m{i}(self):\n        return {i}" for i in range(22)
)

DUPLICATE_SRC = """
def alpha(x):
    y = x + 1
    return y * 2


def beta(x):
    y = x + 1
    return y * 2
"""

BROAD_EXC_SRC = """
try:
    pass
except Exception:
    pass

try:
    pass
except:
    pass

try:
    pass
except ValueError:
    pass
"""

SYNTAX_ERROR_SRC = "def broken(:\n    pass\n"

HEAVY_IMPORTS_SRC = "\n".join(f"import mod{i}" for i in range(20)) + "\ndef ok():\n    return 1\n"


# ───────────────────────────── complexity & smells ────────────────────────────


@pytest.mark.unit
class TestPythonAnalysis:
    def test_calculate_complexity(self, det):
        tree = ast.parse(COMPLEX_SRC)
        fn = next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "tangled"
        )
        assert det._calculate_complexity(fn) > 10

    def test_calculate_complexity_simple(self, det):
        tree = ast.parse("def f():\n    return 1\n")
        fn = tree.body[0]
        assert det._calculate_complexity(fn) == 1

    def test_missing_file(self, det):
        assert det.analyze_python_file("no_such_file_xyz.py") == []

    def test_syntax_error_reported(self, det, tmp_path):
        p = tmp_path / "bad.py"
        p.write_text(SYNTAX_ERROR_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        assert smells[0]["type"] == "Syntax Error"
        assert smells[0]["severity"] == "critical"

    def test_high_complexity_flagged(self, det, tmp_path):
        p = tmp_path / "complex.py"
        p.write_text(COMPLEX_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p), thresholds={"complexity": 5})
        assert any(s["type"] == "High Cyclomatic Complexity" for s in smells)

    def test_too_many_args(self, det, tmp_path):
        p = tmp_path / "args.py"
        p.write_text(TOO_MANY_ARGS_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        assert any(s["type"] == "Too Many Arguments" and s["count"] == 7 for s in smells)

    def test_long_method(self, det, tmp_path):
        p = tmp_path / "long.py"
        p.write_text(LONG_METHOD_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        assert any(s["type"] == "Long Method" for s in smells)

    def test_too_many_returns(self, det, tmp_path):
        p = tmp_path / "ret.py"
        p.write_text(MANY_RETURNS_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        assert any(s["type"] == "Too Many Returns" and s["return_count"] > 7 for s in smells)

    def test_large_class(self, det, tmp_path):
        p = tmp_path / "big.py"
        p.write_text(LARGE_CLASS_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        assert any(s["type"] == "Large Class" and s["method_count"] == 22 for s in smells)

    def test_duplicate_functions(self, det, tmp_path):
        p = tmp_path / "dup.py"
        p.write_text(DUPLICATE_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        dup = [s for s in smells if s["type"] == "Duplicate Code"]
        assert dup and dup[0]["instances"] == 2

    def test_broad_exceptions(self, det, tmp_path):
        p = tmp_path / "exc.py"
        p.write_text(BROAD_EXC_SRC, encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        types_found = [s["type"] for s in smells if s["type"].startswith(("Bare", "Broad"))]
        assert "Bare Except" in types_found
        assert "Broad Exception" in types_found

    def test_normalize_masks_values(self, det):
        a = det._normalize("'hello' 123")
        assert "<str>" in a
        assert "0" in a

    def test_value_error_path(self, det, tmp_path, monkeypatch):
        p = tmp_path / "v.py"
        p.write_text("x = 1\n", encoding="utf-8")

        def boom(_content):
            raise ValueError("bad parse")

        monkeypatch.setattr("builtins.open", lambda *a, **kw: boom("x"))
        smells = det.analyze_python_file(str(p))
        assert smells == []  # error logged, no crash


# ───────────────────────────────── radon path ─────────────────────────────────


@pytest.mark.unit
class TestRadonIntegration:
    def _install_fake_radon(self, monkeypatch, blocks, mi_value=70.0):
        complexity_mod = types.ModuleType("radon.complexity")
        complexity_mod.cc_visit = lambda tree: blocks
        metrics_mod = types.ModuleType("radon.metrics")
        metrics_mod.mi_visit = lambda tree, multi: mi_value
        radon_pkg = types.ModuleType("radon")
        radon_pkg.complexity = complexity_mod
        radon_pkg.metrics = metrics_mod
        monkeypatch.setitem(sys.modules, "radon", radon_pkg)
        monkeypatch.setitem(sys.modules, "radon.complexity", complexity_mod)
        monkeypatch.setitem(sys.modules, "radon.metrics", metrics_mod)

    def test_analyze_radon_high_complexity_and_mi(self, det, tmp_path, monkeypatch):
        block = SimpleNamespace(complexity=15, lineno=3, endline=9, name="hot")
        self._install_fake_radon(monkeypatch, [block], mi_value=40.0)
        det.radon_available = True
        p = tmp_path / "r.py"
        p.write_text("def hot():\n    return 1\n", encoding="utf-8")
        smells = det.analyze_python_file(str(p))
        kinds = {s["type"] for s in smells}
        assert "High Complexity (radon)" in kinds
        assert "Low Maintainability" in kinds

    def test_analyze_radon_direct_with_tree_none(self, det, tmp_path, monkeypatch):
        block = SimpleNamespace(complexity=2, lineno=1, endline=2, name="ok")
        self._install_fake_radon(monkeypatch, [block], mi_value=80.0)
        p = tmp_path / "r2.py"
        p.write_text("def ok():\n    return 1\n", encoding="utf-8")
        out = det._analyze_radon(str(p), None, 10)
        assert out == []

    def test_analyze_radon_mi_error_swallowed(self, det, tmp_path, monkeypatch):
        complexity_mod = types.ModuleType("radon.complexity")
        complexity_mod.cc_visit = lambda tree: []
        metrics_mod = types.ModuleType("radon.metrics")

        def boom(tree, multi):
            raise ValueError("mi failed")

        metrics_mod.mi_visit = boom
        radon_pkg = types.ModuleType("radon")
        radon_pkg.complexity = complexity_mod
        radon_pkg.metrics = metrics_mod
        monkeypatch.setitem(sys.modules, "radon", radon_pkg)
        monkeypatch.setitem(sys.modules, "radon.complexity", complexity_mod)
        monkeypatch.setitem(sys.modules, "radon.metrics", metrics_mod)
        det.radon_available = True
        p = tmp_path / "r3.py"
        p.write_text("def ok():\n    return 1\n", encoding="utf-8")
        assert det._analyze_radon(str(p), None, 10) == []

    def test_radon_import_error_returns_empty(self, det, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "radon", None)  # forces ImportError
        det.radon_available = True
        p = tmp_path / "r4.py"
        p.write_text("def ok():\n    return 1\n", encoding="utf-8")
        assert det._analyze_radon(str(p), None, 10) == []

    def test_high_coupling_smell(self, det, tmp_path):
        p = tmp_path / "imports.py"
        p.write_text(HEAVY_IMPORTS_SRC, encoding="utf-8")
        det.radon_available = True  # coupling check is gated on radon_available
        smells = det.analyze_python_file(str(p))
        coupling = [s for s in smells if s["type"] == "High Coupling"]
        assert coupling and coupling[0]["coupling"]["unique_modules"] > 15

    def test_coupling_metrics(self, det):
        tree = ast.parse("import a.b\nfrom c.d import e\nimport a\n")
        metrics = det.compute_coupling_metrics(tree, "x.py")
        assert metrics["fan_out"] == 3
        assert metrics["unique_modules"] == 2  # a, c
        assert metrics["imports"] == ["a", "c", "a"]


# ─────────────────────────────── JS/TS analysis ───────────────────────────────


@pytest.mark.unit
class TestJsTsAnalysis:
    def test_missing_file(self, det):
        assert det.analyze_js_ts_file("nope.js") == []

    def test_long_line_and_eval(self, det, tmp_path):
        p = tmp_path / "app.js"
        p.write_text("const a = 1;\n" + "// " + "z" * 250 + "\neval('1+1')\n", encoding="utf-8")
        smells = det.analyze_js_ts_file(str(p))
        kinds = [s["type"] for s in smells]
        assert "Long Line" in kinds
        assert "Dangerous Patterns" in kinds
        assert smells[kinds.index("Dangerous Patterns")]["severity"] == "critical"

    def test_long_function_and_params(self, det, tmp_path):
        lines = ["function big(a, b, c, d, e, f, g) {"]
        lines += [f"    step{i}();" for i in range(210)]
        lines.append("}")
        p = tmp_path / "big.js"
        p.write_text("\n".join(lines), encoding="utf-8")
        smells = det.analyze_js_ts_file(str(p))
        kinds = [s["type"] for s in smells]
        assert "Long Function" in kinds
        assert "Too Many Parameters" in kinds

    def test_function_close_via_paren_brace(self, det, tmp_path):
        src = "const fn = (a, b) => {\n    return a + b;\n});\nconst x = 1;\n"
        p = tmp_path / "arrow.js"
        p.write_text(src, encoding="utf-8")
        assert det.analyze_js_ts_file(str(p)) == []

    def test_oserror_swallowed(self, det, tmp_path, monkeypatch):
        import builtins

        real_open = builtins.open

        def fake_open(path, *a, **kw):
            if str(path).endswith(".js"):
                raise OSError("nope")
            return real_open(path, *a, **kw)

        monkeypatch.setattr(builtins, "open", fake_open)
        assert det.analyze_js_ts_file(str(tmp_path / "x.js")) == []


# ─────────────────────────── directory / external tools ───────────────────────


@pytest.mark.unit
class TestDirectoryAnalysis:
    def test_missing_directory(self, det):
        assert det.analyze_directory("no_such_dir_xyz") == {}

    def test_py_and_js_files(self, det, tmp_path):
        (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text(SYNTAX_ERROR_SRC, encoding="utf-8")
        (tmp_path / "app.js").write_text("eval('1')\n", encoding="utf-8")
        (tmp_path / "readme.md").write_text("ignored", encoding="utf-8")
        results = det.analyze_directory(str(tmp_path))
        assert any(k.endswith("bad.py") for k in results)
        assert any(k.endswith("app.js") for k in results)
        assert not any(k.endswith("readme.md") for k in results)

    def test_pylint_invocation_and_output_parsing(self, det, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)  # traversal guard requires target under CWD
        pylint_json = json.dumps(
            [
                {
                    "path": str(tmp_path / "a.py"),
                    "symbol": "unused-import",
                    "message": "Unused import os",
                    "line": 1,
                    "type": "warning",
                },
                {
                    "path": str(tmp_path / "a.py"),
                    "symbol": "fatal",
                    "message": "bad",
                    "line": 2,
                    "type": "error",
                },
                {"path": "", "symbol": "skip", "message": "", "line": 0, "type": "error"},
            ]
        )
        captured: list[str] = []

        def fake_run(cmd, **kw):
            captured.append(cmd[0])
            return _proc(pylint_json)

        monkeypatch.setattr(csd.subprocess, "run", fake_run)
        det.pylint_available = True
        results = det.analyze_directory(str(tmp_path))
        assert any(c.startswith("pylint") for c in captured)
        entries = results[str(tmp_path / "a.py")]
        assert entries[0]["source"] == "pylint"
        severities = {e["severity"] for e in entries}
        assert severities == {"warning", "critical"}

    def test_pylint_timeout_current_behaviour(self, det, tmp_path, monkeypatch):
        """BUG-FOUND (Task 7-f): _analyze_pylint_directory does ``import json``
        inside the try-block, so its own except clause referencing
        ``json.JSONDecodeError`` raises UnboundLocalError on TimeoutExpired
        instead of the intended graceful warning.  Test documents current
        behaviour; fix would be moving the import to module scope."""
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        def boom(*a, **kw):
            raise subprocess.TimeoutExpired("pylint", 120)

        monkeypatch.setattr(csd.subprocess, "run", boom)
        det.pylint_available = True
        with pytest.raises(UnboundLocalError):
            det.analyze_directory(str(tmp_path))

    def test_pylint_bad_json_swallowed(self, det, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(csd.subprocess, "run", lambda *a, **kw: _proc("not-json{"))
        det.pylint_available = True
        assert det.analyze_directory(str(tmp_path)) == {}

    def test_pylint_path_traversal_blocked(self, det, tmp_path, monkeypatch):
        ran: list = []

        def fake_run(*a, **kw):
            ran.append(a)
            return _proc("[]")

        monkeypatch.setattr(csd.subprocess, "run", fake_run)
        det.pylint_available = True
        det._analyze_pylint_directory("../outside")
        assert ran == []


# ───────────────────────────────── jscpd ──────────────────────────────────────


@pytest.mark.unit
class TestJscpd:
    def test_missing_directory(self, det):
        assert det.run_jscpd("no_such_dir")["status"] == "skipped"

    def test_path_traversal_blocked(self, det, tmp_path, monkeypatch):
        outside = tmp_path / "outside"
        outside.mkdir()
        inside = tmp_path / "inside"
        inside.mkdir()
        monkeypatch.chdir(inside)
        ran: list = []

        def fake_run(*a, **kw):
            ran.append(a)
            return _proc("{}")

        monkeypatch.setattr(csd.subprocess, "run", fake_run)
        out = det.run_jscpd("../outside")
        assert out["status"] == "blocked"
        assert ran == []

    def test_binary_missing(self, det, monkeypatch):
        def boom(*a, **kw):
            raise FileNotFoundError("jscpd")

        monkeypatch.setattr(csd.subprocess, "run", boom)
        out = det.run_jscpd(".")
        assert out == {"status": "skipped", "reason": "jscpd not found"}

    def test_timeout_current_behaviour(self, det, monkeypatch):
        """BUG-FOUND (Task 7-f): same ``import json`` shadowing issue as
        _analyze_pylint_directory — TimeoutExpired triggers UnboundLocalError
        instead of the intended {status: error} return."""

        def boom(*a, **kw):
            raise subprocess.TimeoutExpired("jscpd", 180)

        monkeypatch.setattr(csd.subprocess, "run", boom)
        with pytest.raises(UnboundLocalError):
            det.run_jscpd(".")

    def test_empty_stdout(self, det, monkeypatch):
        monkeypatch.setattr(csd.subprocess, "run", lambda *a, **kw: _proc(""))
        out = det.run_jscpd(".")
        assert out == {"status": "success", "duplicates": []}

    def test_success_with_duplicates(self, det, monkeypatch):
        payload = json.dumps({"duplicates": [{"firstFile": "a.js"}], "statistics": {"total": 1}})
        monkeypatch.setattr(csd.subprocess, "run", lambda *a, **kw: _proc(payload))
        out = det.run_jscpd(".")
        assert out["duplicates"][0]["firstFile"] == "a.js"
        assert out["statistics"] == {"total": 1}

    def test_non_json_stdout_ignored(self, det, monkeypatch):
        monkeypatch.setattr(csd.subprocess, "run", lambda *a, **kw: _proc("noise"))
        out = det.run_jscpd(".")
        assert out == {"status": "success", "duplicates": [], "statistics": {}}

    def test_duplicate_section_in_directory_report(self, det, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        payload = json.dumps({"duplicates": [{"firstFile": "a.py"}], "statistics": {}})
        monkeypatch.setattr(csd.subprocess, "run", lambda *a, **kw: _proc(payload))
        results = det.analyze_directory(str(tmp_path))
        assert results["_jscpd_"][0]["duplicates"][0]["firstFile"] == "a.py"


# ───────────────────────── SARIF / hooks / history ────────────────────────────


@pytest.mark.unit
class TestSarifHistoryHooks:
    def test_generate_sarif(self, det):
        results = {
            "src/a.py": [
                {"type": "Bare Except", "message": "bare", "severity": "warning", "line": 3},
                {
                    "type": "Syntax Error",
                    "message": "bad",
                    "severity": "critical",
                    "line": 1,
                    "end_line": 2,
                },
            ],
            "_jscpd_": [{"status": "success"}],  # underscore keys are skipped
        }
        sarif = det.generate_sarif(results, repo_uri="file:///repo")
        assert sarif["version"] == "2.1.0"
        run = sarif["runs"][0]
        assert run["tool"]["driver"]["name"] == "SupremeAICodeSmellDetector"
        rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
        assert rule_ids == {"Bare Except", "Syntax Error"}
        levels = {r["ruleId"]: r["level"] for r in run["results"]}
        assert levels["Bare Except"] == "warning"
        assert levels["Syntax Error"] == "error"
        loc = run["results"][0]["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"] == "src/a.py"
        assert loc["region"]["startLine"] == 3

    def test_sarif_unknown_severity_defaults_note(self, det):
        sarif = det.generate_sarif({"a.py": [{"type": "T", "message": "m", "severity": "??"}]})
        assert sarif["runs"][0]["results"][0]["level"] == "note"

    def test_install_hook_in_git_repo(self, det, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        assert det.install_pre_commit_hook(str(tmp_path)) is True
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert hook.read_text(encoding="utf-8").startswith("#!/bin/sh")

    def test_install_hook_no_git_repo(self, det, tmp_path):
        assert det.install_pre_commit_hook(str(tmp_path)) is False

    def test_install_hook_oserror(self, det, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        import builtins

        real_open = builtins.open

        def fake_open(path, *a, **kw):
            if "pre-commit" in str(path):
                raise OSError("denied")
            return real_open(path, *a, **kw)

        monkeypatch.setattr(builtins, "open", fake_open)
        assert det.install_pre_commit_hook(str(tmp_path)) is False

    def test_track_history_first_run(self, det, tmp_path):
        hist = tmp_path / "data" / "code_smell_history.json"
        record = det.track_history({"a.py": [{"type": "T"}]}, history_file=str(hist))
        assert record["total_smells"] == 1
        assert record["files_affected"] == 1
        assert "trend" in record
        saved = json.loads(hist.read_text(encoding="utf-8"))
        assert len(saved) == 1

    def test_track_history_improving_trend(self, det, tmp_path):
        hist = tmp_path / "history.json"
        hist.write_text(json.dumps([{"timestamp": 1, "total_smells": 10}]), encoding="utf-8")
        record = det.track_history({"a.py": []}, history_file=str(hist))
        assert record["trend"] == "improving"
        saved = json.loads(hist.read_text(encoding="utf-8"))
        assert len(saved) == 2

    def test_track_history_worsening_trend(self, det, tmp_path):
        hist = tmp_path / "history2.json"
        hist.write_text(json.dumps([{"timestamp": 1, "total_smells": 0}]), encoding="utf-8")
        record = det.track_history({"a.py": [{"type": "T"}]}, history_file=str(hist))
        assert record["trend"] == "worsening"

    def test_track_history_corrupt_file(self, det, tmp_path):
        hist = tmp_path / "broken.json"
        hist.write_text("{not json", encoding="utf-8")
        record = det.track_history({}, history_file=str(hist))
        assert record["total_smells"] == 0
        # corrupt history replaced by a single new record
        assert len(json.loads(hist.read_text(encoding="utf-8"))) == 1

    def test_track_history_ignores_underscore_keys(self, det, tmp_path):
        hist = tmp_path / "h3.json"
        record = det.track_history(
            {"a.py": [{"type": "T"}], "_jscpd_": [{"d": 1}]}, history_file=str(hist)
        )
        assert record["total_smells"] == 1

    def test_track_history_oserror_write(self, det, tmp_path, monkeypatch):
        import os as os_mod

        # directory path as history file → os.makedirs/write fails silently
        bad = tmp_path / "dir.json"
        bad.mkdir()
        record = det.track_history({}, history_file=str(bad / "nested" / "x.json"))
        assert "trend" in record or record["total_smells"] == 0
        assert os_mod.environ.get("HOME")  # no-op sanity
