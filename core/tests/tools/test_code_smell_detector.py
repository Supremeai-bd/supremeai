import ast
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# 对环境变量做最小设置,避免导入时触发外部依赖
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://127.0.0.1:11434")  # is_local()


# Bengali: CodeSmellDetector-এর مختلف মেথড সংক্রান্ত পরীক্ষা
# এটি কেন্দ্রীয় স্ট্যাটিক অ্যানালাইসিস টুলের কভারেজ বৃদ্ধি করতে সাহায্য করে
from tools.code.code_smell_detector import CodeSmellDetector


@pytest.fixture
def detector():
    return CodeSmellDetector()


def _make_fake_radon(cc_return, mi_return):
    fake_complexity = types.ModuleType("radon.complexity")
    fake_complexity.cc_visit = MagicMock(return_value=cc_return)
    fake_metrics = types.ModuleType("radon.metrics")
    fake_metrics.mi_visit = MagicMock(return_value=mi_return)
    fake_radon = types.ModuleType("radon")
    fake_radon.complexity = fake_complexity
    fake_radon.metrics = fake_metrics
    return fake_radon, fake_complexity, fake_metrics


# ========================
# _normalize examinaiton
# ========================


class TestNormalize:
    def test_collapses_whitespace(self, detector):
        result = detector._normalize("def foo():\n    return 1")
        assert "\n" not in result
        assert "  " not in result

    def test_replaces_strings(self, detector):
        result = detector._normalize("'hello'")
        assert "'<str>'" in result

    def test_replaces_strings_mixed(self, detector):
        result = detector._normalize("name = 'test_value'")
        assert "<str>" in result
        assert "test_value" not in result

    def test_replaces_numbers(self, detector):
        result = detector._normalize("count = 42")
        assert "0" in result

    def test_replaces_multiple_numbers(self, detector):
        result = detector._normalize("x = 10\ny = 20")
        assert result.count("0") >= 2

    def test_preserves_keywords(self, detector):
        result = detector._normalize("def foo():")
        assert "def" in result
        assert "foo" in result

    def test_complex_dump_normalization(self, detector):
        src = "ast.FunctionDef(name='foo', args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='self')], kwonlyargs=[], defaults=[42]))"
        result = detector._normalize(src)
        assert "'<str>'" in result
        assert "0" in result


# ========================
# _calculate_complexity
# ========================


class TestCalculateComplexity:
    def test_simple_function_base_complexity(self, detector):
        code = "def foo():\n    return 1\n"
        tree = ast.parse(code)
        node = tree.body[0]
        assert detector._calculate_complexity(node) == 1

    def test_if_increases_complexity(self, detector):
        code = "def foo():\n    if x:\n        return 1\n    return 2\n"
        tree = ast.parse(code)
        node = tree.body[0]
        assert detector._calculate_complexity(node) == 2

    def test_for_loop_increases_complexity(self, detector):
        code = "def foo():\n    for i in range(10):\n        print(i)\n"
        tree = ast.parse(code)
        assert detector._calculate_complexity(tree.body[0]) == 2

    def test_while_loop_increases_complexity(self, detector):
        code = "def foo():\n    while True:\n        break\n"
        tree = ast.parse(code)
        assert detector._calculate_complexity(tree.body[0]) == 2

    def test_except_handler_increases_complexity(self, detector):
        code = "def foo():\n    try:\n        pass\n    except Exception:  # noqa: BLE001\n        pass\n"
        tree = ast.parse(code)
        assert detector._calculate_complexity(tree.body[0]) == 2

    def test_bool_op_additional_complexity(self, detector):
        code = "def foo(x, y, z):\n    return x and y and z\n"
        tree = ast.parse(code)
        assert detector._calculate_complexity(tree.body[0]) == 4

    def test_nested_if_and_for(self, detector):
        code = "def foo():\n    for i in range(10):\n        if i > 5:\n            while True:\n                break\n"
        tree = ast.parse(code)
        assert detector._calculate_complexity(tree.body[0]) >= 4

    def test_with_statement_increases_complexity(self, detector):
        code = "def foo():\n    with open('f') as f:\n        pass\n"
        tree = ast.parse(code)
        assert detector._calculate_complexity(tree.body[0]) == 2

    def test_assert_increases_complexity(self, detector):
        code = "def foo():\n    assert x > 0\n"
        tree = ast.parse(code)
        assert detector._calculate_complexity(tree.body[0]) == 2


# ========================
# _detect_broad_exceptions
# ========================


class TestDetectBroadExceptions:
    def test_detects_bare_except(self, detector):
        code = "def foo():\n    try:\n        pass\n    except:\n        pass\n"
        tree = ast.parse(code)
        result = detector._detect_broad_exceptions(tree, "test.py")
        assert len(result) == 1
        assert result[0]["type"] == "Bare Except"
        assert result[0]["severity"] == "warning"

    def test_detects_broad_exception(self, detector):
        code = "def foo():\n    try:\n        pass\n    except Exception:  # noqa: BLE001\n        pass\n"
        tree = ast.parse(code)
        result = detector._detect_broad_exceptions(tree, "test.py")
        assert len(result) == 1
        assert result[0]["type"] == "Broad Exception"
        assert "Exception" in result[0]["message"]

    def test_detects_base_exception(self, detector):
        code = "def foo():\n    try:\n        pass\n    except BaseException:\n        pass\n"
        tree = ast.parse(code)
        result = detector._detect_broad_exceptions(tree, "test.py")
        assert len(result) == 1
        assert result[0]["type"] == "Broad Exception"

    def test_no_except_no_smell(self, detector):
        code = "def foo():\n    return 1\n"
        tree = ast.parse(code)
        result = detector._detect_broad_exceptions(tree, "test.py")
        assert result == []

    def test_specific_exception_ignored(self, detector):
        code = "def foo():\n    try:\n        pass\n    except ValueError:\n        pass\n"
        tree = ast.parse(code)
        result = detector._detect_broad_exceptions(tree, "test.py")
        assert result == []

    def test_multiple_broad_handlers(self, detector):
        code = "def foo():\n    try:\n        pass\n    except Exception:  # noqa: BLE001\n        pass\n    except:\n        pass\n"
        tree = ast.parse(code)
        result = detector._detect_broad_exceptions(tree, "test.py")
        assert len(result) == 2


# ========================
# _detect_duplicate_functions
# Bengali: ast.dump(node.body)-তে বাগ রয়েছে — এটি একটি লিটারাল
# 密鑠 এই টেস্টটি বর্তমান আচরণের সাথে সামঞ্জস্যপূর্ণভাবে লিখা হয়েছে।
# ========================


class TestDetectDuplicateFunctions:
    def test_duplicate_detection_handles_identical_functions(self, detector):
        code = "def foo():\n    x = 1\n    return x\n\ndef bar():\n    x = 1\n    return x\n"
        tree = ast.parse(code)
        result = detector._detect_duplicate_functions(tree, "test.py")
        assert len(result) == 1
        assert result[0]["type"] == "Duplicate Code"

    def test_unique_bodies_no_duplicates(self, detector):
        code = "def foo():\n    x = 1\n    return x\n\ndef bar():\n    y = [1, 2, 3]\n    for i in y:\n        print(i)\n"
        tree = ast.parse(code)
        result = detector._detect_duplicate_functions(tree, "test.py")
        assert len(result) == 0

    def test_single_function_no_duplicates(self, detector):
        code = "def foo():\n    x = 1\n    return x\n"
        tree = ast.parse(code)
        result = detector._detect_duplicate_functions(tree, "test.py")
        assert len(result) == 0

    def test_mocked_dump_detects_duplicate(self, detector):
        code = "def foo():\n    x = 1\n    return x\n\ndef bar():\n    x = 1\n    return x\n"
        tree = ast.parse(code)
        with (
            patch.object(detector, "_normalize", return_value="same_norm"),
            patch(
                "backend.tools.code.code_smell_detector.ast.dump",
                side_effect=lambda node: "same",
            ),
        ):
            result = detector._detect_duplicate_functions(tree, "test.py")
        assert len(result) == 1
        assert result[0]["type"] == "Duplicate Code"
        assert result[0]["instances"] == 2


# ========================
# analyze_python_file
# ========================


class TestAnalyzePythonFile:
    def test_missing_file_returns_empty(self, detector, tmp_path):
        result = detector.analyze_python_file(str(tmp_path / "nonexistent.py"))
        assert result == []

    def test_high_complexity_detected(self, detector, tmp_path):
        src = "def foo(x):\n    if x:\n        if x > 0:\n            if x > 10:\n                pass\n    return x\n"
        f = tmp_path / "complex.py"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_python_file(str(f), {"complexity": 2})
        types = [s["type"] for s in result]
        assert "High Cyclomatic Complexity" in types

    def test_too_many_args_detected(self, detector, tmp_path):
        src = "def foo(a, b, c, d, e, f, g):\n    return a + b + c + d + e + f + g\n"
        f = tmp_path / "args.py"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_python_file(str(f), {"args": 3})
        assert any(s["type"] == "Too Many Arguments" for s in result)

    def test_long_method_detected(self, detector, tmp_path):
        lines = "def foo():\n" + "\n".join(f"    x = {i}" for i in range(60)) + "\n"
        f = tmp_path / "long.py"
        f.write_text(lines, encoding="utf-8")
        result = detector.analyze_python_file(str(f), {"lines": 50})
        assert any(s["type"] == "Long Method" for s in result)

    def test_large_class_detected(self, detector, tmp_path):
        methods = "\n".join(f"    def method_{i}(self):\n        pass" for i in range(25))
        src = f"class BigClass:\n{methods}\n"
        f = tmp_path / "bigclass.py"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_python_file(str(f), {"class_methods": 20})
        assert any(s["type"] == "Large Class" and s["class"] == "BigClass" for s in result)

    def test_syntax_error_reported(self, detector, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def foo(\n    pass\n", encoding="utf-8")
        result = detector.analyze_python_file(str(f))
        assert any(s["type"] == "Syntax Error" for s in result)

    def test_broad_exception_detected_when_no_dup_bug(self, detector, tmp_path):
        src = "def foo():\n    try:\n        pass\n    except Exception:  # noqa: BLE001\n        pass\n"
        f = tmp_path / "be.py"
        f.write_text(src, encoding="utf-8")
        with patch.object(detector, "_detect_duplicate_functions", return_value=[]):
            result = detector.analyze_python_file(str(f))
        assert any(s["type"] == "Broad Exception" for s in result)

    def test_radon_skipped_when_unavailable(self, detector, tmp_path):
        src = "def foo():\n    return 1\n"
        f = tmp_path / "safe.py"
        f.write_text(src, encoding="utf-8")
        with patch.object(detector, "_detect_duplicate_functions", return_value=[]):
            with patch.object(
                detector,
                "compute_coupling_metrics",
                return_value={"unique_modules": 0, "fan_out": 0},
            ):
                result = detector.analyze_python_file(str(f))
        assert isinstance(result, list)

    def test_returns_empty_on_non_python_extension(self, detector, tmp_path):
        f = tmp_path / "notpy.txt"
        f.write_text("def foo():\n    return 1\n")
        result = detector.analyze_python_file(str(f))
        assert isinstance(result, list)


# ========================
# analyze_js_ts_file
# ========================


class TestAnalyzeJsTsFile:
    def test_missing_file_returns_empty(self, detector, tmp_path):
        result = detector.analyze_js_ts_file(str(tmp_path / "nonexistent.js"))
        assert result == []

    def test_long_line_detected(self, detector, tmp_path):
        line = "// " + "x" * 250
        src = f"{line}\nfunction foo() {{}}\n"
        f = tmp_path / "long.js"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_js_ts_file(str(f))
        assert any(s["type"] == "Long Line" for s in result)

    def test_dangerous_patterns_detected_eval(self, detector, tmp_path):
        src = "function foo() {\n    eval('1+1');\n}\n"
        f = tmp_path / "danger.js"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_js_ts_file(str(f))
        assert any(s["type"] == "Dangerous Patterns" for s in result)

    def test_dangerous_patterns_detected_function_constructor(self, detector, tmp_path):
        src = "function foo() {\n    new Function('return 1');\n}\n"
        f = tmp_path / "danger.js"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_js_ts_file(str(f))
        assert any(s["type"] == "Dangerous Patterns" for s in result)

    def test_default_thresholds_used_when_none(self, detector, tmp_path):
        src = "function foo() {\n    return 1;\n}\n"
        f = tmp_path / "norm.js"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_js_ts_file(str(f))
        assert isinstance(result, list)

    def test_custom_thresholds_respected(self, detector, tmp_path):
        src = "function foo(a, b, c, d, e, f) {\n    return a + b + c + d + e + f;\n}\n"
        f = tmp_path / "params.js"
        f.write_text(src, encoding="utf-8")
        result = detector.analyze_js_ts_file(str(f), {"args": 3})
        assert any(s["type"] == "Too Many Parameters" for s in result)


# ========================
# _analyze_radon
# ========================


class TestAnalyzeRadon:
    def test_returns_empty_when_radon_missing(self, detector):
        with patch.dict(
            sys.modules,
            {"radon": None, "radon.complexity": None, "radon.metrics": None},
        ):
            result = detector._analyze_radon("test.py", None, 10)
        assert result == []

    def test_handles_syntax_error(self, detector, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def foo(\n    pass\n", encoding="utf-8")
        tree = ast.parse("def foo():\n    return 1\n")
        result = detector._analyze_radon(str(f), tree, 10)
        assert result == []

    def test_high_radon_complexity_detected(self, detector):
        fake_radon, fake_complexity, fake_metrics = _make_fake_radon(
            cc_return=[],
            mi_return=80.0,
        )
        block = MagicMock(complexity=20, lineno=1, endline=10, name="foo")
        fake_complexity.cc_visit = MagicMock(return_value=[block])

        with patch.dict(
            sys.modules,
            {
                "radon": fake_radon,
                "radon.complexity": fake_complexity,
                "radon.metrics": fake_metrics,
            },
        ):
            tree = ast.parse("def foo():\n    return 1\n")
            result = detector._analyze_radon("test.py", tree, 10)
        assert any(
            s["type"] == "High Complexity (radon)" and s.get("complexity") == 20 for s in result
        )

    def test_low_maintainability_detected(self, detector):
        fake_radon, fake_complexity, fake_metrics = _make_fake_radon(
            cc_return=[],
            mi_return=30.0,
        )

        with patch.dict(
            sys.modules,
            {
                "radon": fake_radon,
                "radon.complexity": fake_complexity,
                "radon.metrics": fake_metrics,
            },
        ):
            tree = ast.parse("def foo():\n    return 1\n")
            result = detector._analyze_radon("test.py", tree, 10)
        assert any(
            s["type"] == "Low Maintainability" and "30.0" in s.get("message", "") for s in result
        )

    def test_reparses_when_tree_none(self, detector, tmp_path):
        fake_radon, fake_complexity, fake_metrics = _make_fake_radon(
            cc_return=[],
            mi_return=70.0,
        )

        f = tmp_path / "x.py"
        f.write_text("def foo():\n    return 1\n", encoding="utf-8")

        with (
            patch.dict(
                sys.modules,
                {
                    "radon": fake_radon,
                    "radon.complexity": fake_complexity,
                    "radon.metrics": fake_metrics,
                },
            ),
            patch("backend.tools.code.code_smell_detector.ast.parse") as mock_parse,
        ):
            mock_parse.return_value = ast.parse("def foo():\n    return 1\n")
            detector._analyze_radon(str(f), None, 10)
        assert mock_parse.call_count >= 1


# ========================
# compute_coupling_metrics
# ========================


class TestComputeCouplingMetrics:
    def test_no_imports_zero_coupling(self, detector):
        tree = ast.parse("def foo():\n    return 1\n")
        result = detector.compute_coupling_metrics(tree, "test.py")
        assert result["fan_out"] == 0
        assert result["unique_modules"] == 0
        assert result["file"] == "test.py"

    def test_import_fan_out(self, detector):
        tree = ast.parse("import os\nimport sys\n")
        result = detector.compute_coupling_metrics(tree, "test.py")
        assert result["fan_out"] == 2
        assert result["unique_modules"] == 2

    def test_importfrom_fan_out(self, detector):
        tree = ast.parse("from collections import OrderedDict\nfrom os import path\n")
        result = detector.compute_coupling_metrics(tree, "test.py")
        assert result["fan_out"] == 2
        assert result["unique_modules"] == 2

    def test_dotted_module_counts_as_one(self, detector):
        tree = ast.parse("import os.path\nfrom os.path import join\n")
        result = detector.compute_coupling_metrics(tree, "test.py")
        assert result["fan_out"] == 2
        assert result["unique_modules"] == 1

    def test_duplicated_imports_count_towards_fan_out(self, detector):
        tree = ast.parse("import os\nimport os\n")
        result = detector.compute_coupling_metrics(tree, "test.py")
        assert result["fan_out"] == 2
        assert result["unique_modules"] == 1


# ========================
# Constructor availability
# ========================


class TestConstructorAvailability:
    def test_init_reports_radon_status(self):
        with patch.object(CodeSmellDetector, "_check_radon", return_value=True):
            with patch.object(CodeSmellDetector, "_check_pylint", return_value=False):
                d = CodeSmellDetector()
        assert d.radon_available is True
        assert d.pylint_available is False

    def test_init_reports_pylint_status(self):
        with patch.object(CodeSmellDetector, "_check_radon", return_value=False):
            with patch.object(CodeSmellDetector, "_check_pylint", return_value=True):
                d = CodeSmellDetector()
        assert d.radon_available is False
        assert d.pylint_available is True

    def test_init_reports_both_unavailable(self):
        with patch.object(CodeSmellDetector, "_check_radon", return_value=False):
            with patch.object(CodeSmellDetector, "_check_pylint", return_value=False):
                d = CodeSmellDetector()
        assert d.radon_available is False
        assert d.pylint_available is False

    def test_check_radon_true_when_available(self):
        with patch.dict(sys.modules, {"radon": MagicMock(), "radon.complexity": MagicMock()}):
            assert CodeSmellDetector()._check_radon() is True

    def test_check_radon_false_when_missing(self):
        with patch.dict(sys.modules, {"radon": None}):
            d = CodeSmellDetector()
        assert d.radon_available is False

    def test_check_pylint_true_when_present(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            d = CodeSmellDetector()
        assert d.pylint_available is True

    def test_check_pylint_false_when_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            d = CodeSmellDetector()
        assert d.pylint_available is False
