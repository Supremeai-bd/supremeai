"""Full-coverage tests for core.security.scanning.ast_scanner.

বাংলা: স্যান্ডবক্স AST স্ক্যানারের প্রতিটি পাবলিক API, ব্রাঞ্চ ও এজ কেস কভার করে।
Pure-logic tests — no I/O, no network.
"""

from __future__ import annotations

import pytest

from core.security.scanning.ast_scanner import (
    BLOCKED_BUILTIN_FUNCTIONS,
    BLOCKED_DUNDER_PATTERNS,
    BLOCKED_MODULES,
    SANDBOX_ESCAPE_PATTERNS,
    ASTSandboxScanner,
    ScanResult,
    _SandboxVisitor,
    scan_code,
    validate_code_for_sandbox,
)

pytestmark = pytest.mark.security


SAFE_SNIPPET = "x = 1 + 2\nprint(x)\n"


class TestConstants:
    """Sanity-check the scanner's blocked-pattern constants."""

    def test_blocked_builtins_contains_core_dangerous_functions(self):
        for fn in ("getattr", "eval", "exec", "open", "__import__"):
            assert fn in BLOCKED_BUILTIN_FUNCTIONS

    def test_blocked_modules_contains_os_and_subprocess(self):
        assert "os" in BLOCKED_MODULES
        assert "subprocess" in BLOCKED_MODULES
        assert "socket" in BLOCKED_MODULES

    def test_blocked_dunder_patterns_contains_escape_dunders(self):
        assert "__class__" in BLOCKED_DUNDER_PATTERNS
        assert "__subclasses__" in BLOCKED_DUNDER_PATTERNS

    def test_sandbox_escape_patterns_are_compiled_regexes(self):
        # Each pattern is a compiled regex; the class-chaining ones match the
        # canonical escape string while others target different vectors.
        assert all(getattr(p, "pattern", None) for p in SANDBOX_ESCAPE_PATTERNS)
        assert any(p.search("__class__.__bases__") for p in SANDBOX_ESCAPE_PATTERNS)
        assert any(p.search("obj.__subclasses__ ()") for p in SANDBOX_ESCAPE_PATTERNS)
        assert any(p.search("x.__globals__ [") for p in SANDBOX_ESCAPE_PATTERNS)
        assert any(p.search("o.__reduce__ (") for p in SANDBOX_ESCAPE_PATTERNS)
        assert any(p.search("object ()") for p in SANDBOX_ESCAPE_PATTERNS)


class TestScanResult:
    def test_default_result_is_safe_pass(self):
        result = ScanResult()
        assert result.is_safe is True
        assert result.severity == "PASS"
        assert result.findings == []
        assert result.blocked_builtins == []
        assert result.blocked_imports == []
        assert result.dunder_accesses == []
        assert result.escape_patterns == []


class TestASTSandboxScannerScan:
    def setup_method(self):
        self.scanner = ASTSandboxScanner(strict_mode=True)

    def test_empty_code_is_safe(self):
        result = self.scanner.scan("")
        assert result.is_safe is True
        assert result.severity == "PASS"

    def test_whitespace_only_code_is_safe(self):
        result = self.scanner.scan("   \n\t  \n")
        assert result.is_safe is True

    def test_syntax_error_is_unsafe_high(self):
        result = self.scanner.scan("def broken(:\n")
        assert result.is_safe is False
        assert result.severity == "HIGH"
        assert any("Syntax error" in f for f in result.findings)

    def test_safe_code_passes(self):
        result = self.scanner.scan(SAFE_SNIPPET)
        assert result.is_safe is True
        assert result.severity == "PASS"
        assert result.findings == []

    def test_blocked_builtin_call(self):
        result = self.scanner.scan("getattr(obj, 'name')\n")
        assert result.is_safe is False
        assert "getattr" in result.blocked_builtins
        assert result.severity in {"HIGH", "CRITICAL"}

    def test_eval_exec_open_blocked(self):
        for code in ("eval('1+1')\n", "exec('pass')\n", "open('/etc/passwd')\n"):
            result = self.scanner.scan(code)
            assert result.is_safe is False
            assert result.blocked_builtins

    def test_method_call_on_blocked_builtin_name(self):
        # node.func is an Attribute whose attr is a blocked builtin name
        result = self.scanner.scan("helper.getattr(obj, 'x')\n")
        assert "getattr" in result.blocked_builtins
        assert result.is_safe is False

    def test_getattr_with_dunder_string_arg_is_escape(self):
        result = self.scanner.scan("getattr(obj, '__class__')\n")
        assert result.is_safe is False
        assert result.severity == "CRITICAL"
        assert any("sandbox escape attempt" in f for f in result.escape_patterns)
        # NOTE: the getattr-string branch adds to blocked_builtins + escape_patterns
        # only (documenting current behaviour — dunder_accesses is not touched).

    def test_getattr_with_non_dunder_arg_is_not_escape(self):
        result = self.scanner.scan("getattr(obj, 'normal_attr')\n")
        assert "getattr" in result.blocked_builtins
        assert result.escape_patterns == []

    def test_dunder_attribute_access_strict(self):
        result = self.scanner.scan("cls = obj.__class__\n")
        assert result.is_safe is False
        assert "__class__" in result.dunder_accesses
        assert result.severity in {"HIGH", "CRITICAL"}

    def test_chained_dunder_access_is_escape(self):
        result = self.scanner.scan("bases = obj.__class__.__bases__\n")
        assert result.is_safe is False
        assert result.severity == "CRITICAL"
        assert any("Chained dunder access" in f for f in result.escape_patterns)

    def test_reduce_call_is_escape(self):
        result = self.scanner.scan("payload = obj.__reduce__()\n")
        assert result.is_safe is False
        assert result.severity == "CRITICAL"
        assert "__reduce__" in result.dunder_accesses

    def test_reduce_ex_call_is_escape(self):
        result = self.scanner.scan("payload = obj.__reduce_ex__(2)\n")
        assert "__reduce_ex__" in result.dunder_accesses
        assert any("__reduce_ex__() call" in f for f in result.escape_patterns)

    def test_subscript_globals_is_escape(self):
        result = self.scanner.scan("g = fn['__globals__']\n")
        assert result.is_safe is False
        assert result.severity == "CRITICAL"
        assert any("Dict access" in f for f in result.escape_patterns)

    def test_subscript_builtins_is_escape(self):
        result = self.scanner.scan("b = mod['__builtins__']\n")
        assert any("subscript['__builtins__']" in d for d in result.dunder_accesses)

    def test_subscript_dict_is_escape(self):
        result = self.scanner.scan("d = obj['__dict__']\n")
        assert any("subscript['__dict__']" in d for d in result.dunder_accesses)

    def test_subscript_normal_key_is_safe(self):
        result = self.scanner.scan("v = d['normal_key']\n")
        assert result.is_safe is True

    def test_import_blocked_module_strict(self):
        result = self.scanner.scan("import os\n")
        assert result.is_safe is False
        assert "os" in result.blocked_imports
        assert any("Blocked module imports" in f for f in result.findings)

    def test_import_submodule_blocked_by_base(self):
        result = self.scanner.scan("import os.path\n")
        assert "os.path" in result.blocked_imports

    def test_import_safe_module_strict_passes(self):
        result = self.scanner.scan("import math, json\n")
        assert result.is_safe is True
        assert result.blocked_imports == []

    def test_import_unknown_module_strict_blocked(self):
        result = self.scanner.scan("import exotically_named_module\n")
        assert result.is_safe is False
        assert "exotically_named_module" in result.blocked_imports

    def test_import_from_blocked_module(self):
        result = self.scanner.scan("from subprocess import run\n")
        assert result.is_safe is False
        assert "subprocess" in result.blocked_imports

    def test_import_from_safe_module_strict_passes(self):
        result = self.scanner.scan("from decimal import Decimal\n")
        assert result.is_safe is True

    def test_non_strict_blocked_import_logged_not_blocking(self):
        scanner = ASTSandboxScanner(strict_mode=False)
        result = scanner.scan("import os\n")
        # In non-strict mode blocked imports are only logged
        assert result.is_safe is True
        assert result.severity == "PASS"
        assert any("non-strict mode, logged only" in f for f in result.findings)

    def test_non_strict_unknown_import_allowed(self):
        scanner = ASTSandboxScanner(strict_mode=False)
        result = scanner.scan("import exotically_named_module\n")
        assert result.is_safe is True

    def test_non_strict_dunder_logged_not_blocking(self):
        scanner = ASTSandboxScanner(strict_mode=False)
        result = scanner.scan("c = obj.__class__\n")
        assert result.is_safe is True
        assert any("Dunder access detected (non-strict mode" in f for f in result.findings)

    def test_try_block_children_still_visited(self):
        code = "try:\n    eval('1')\nexcept Exception:\n    pass\n"
        result = self.scanner.scan(code)
        assert "eval" in result.blocked_builtins

    def test_text_pattern_escape_detected(self):
        # The string content contains a raw escape pattern — AST-parseable but
        # flagged by the text-based fallback scanner.
        code = 's = "__class__.__bases__"\n'
        result = self.scanner.scan(code)
        assert result.is_safe is False
        assert result.severity == "CRITICAL"
        assert any("Sandbox escape pattern detected" in f for f in result.findings)

    def test_encoded_payload_indicator_non_escaping(self):
        code = "import base64\nvalue = 'safe'\n"
        result = self.scanner.scan(code)
        assert any("Encoded payload indicator" in f for f in result.findings)
        # "base64" indicator alone does not flip safety
        assert result.is_safe is True

    def test_combined_findings_escalate_severity(self):
        code = "import os\ngetattr(obj, '__class__')\n"
        result = self.scanner.scan(code)
        assert result.is_safe is False
        assert result.severity == "CRITICAL"
        assert result.blocked_imports and result.blocked_builtins


class TestSandboxVisitorDirect:
    """Directly exercise the visitor for branch-level coverage."""

    def test_visitor_init_defaults(self):
        visitor = _SandboxVisitor(True, frozenset({"math"}))
        assert visitor.strict_mode is True
        assert visitor.blocked_builtins == set()
        assert visitor.blocked_imports == set()
        assert visitor.dunder_accesses == set()
        assert visitor.escape_patterns == set()

    def test_visit_import_strict_empty_safe_list(self):
        import ast

        visitor = _SandboxVisitor(True, frozenset())
        visitor.visit(ast.parse("import math"))
        # strict mode with an empty allowlist blocks even stdlib-safe imports
        assert "math" in visitor.blocked_imports

    def test_visit_import_non_strict(self):
        import ast

        visitor = _SandboxVisitor(False, frozenset({"math"}))
        visitor.visit(ast.parse("import math"))
        assert visitor.blocked_imports == set()

    def test_visit_import_from_without_module(self):
        import ast

        visitor = _SandboxVisitor(True, frozenset())
        # `from . import sibling` produces ImportFrom with module=None
        tree = ast.parse("from . import sibling")
        visitor.visit(tree)
        assert visitor.blocked_imports == set()


class TestConvenienceFunctions:
    def test_scan_code_safe(self):
        result = scan_code(SAFE_SNIPPET)
        assert isinstance(result, ScanResult)
        assert result.is_safe is True

    def test_scan_code_unsafe_strict(self):
        result = scan_code("getattr(obj, '__class__')\n")
        assert result.is_safe is False
        assert "getattr" in result.blocked_builtins

    def test_scan_code_non_strict(self):
        result = scan_code("import os\n", strict_mode=False)
        assert result.is_safe is True

    def test_validate_code_for_sandbox_safe(self):
        is_safe, reason = validate_code_for_sandbox(SAFE_SNIPPET)
        assert is_safe is True
        assert reason == ""

    def test_validate_code_for_sandbox_unsafe(self):
        is_safe, reason = validate_code_for_sandbox("import os\neval('x')\n")
        assert is_safe is False
        assert "Blocked module imports" in reason
        assert "Blocked builtin functions" in reason

    def test_validate_code_for_sandbox_non_strict(self):
        is_safe, reason = validate_code_for_sandbox("import os\n", strict_mode=False)
        assert is_safe is True
        assert reason == ""
