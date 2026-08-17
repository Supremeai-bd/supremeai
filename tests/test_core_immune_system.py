# tests/test_core_immune_system.py
"""Tests for the ImmuneSystem security scanner."""

import pytest
import ast
from unittest.mock import MagicMock, patch


class TestImmuneSystemScanner:
    """Test the main ImmuneSystem scanner class."""

    def test_scan_code_returns_dict(self):
        """Test that scan_code returns proper dict structure."""
        from backend.core.immune_system import ImmuneSystemScanner

        scanner = ImmuneSystemScanner()
        result = scanner.scan_code("def safe(): pass")

        assert isinstance(result, dict)
        assert "safe" in result

    def test_scan_empty_code(self):
        """Test scanning empty code."""
        from backend.core.immune_system import ImmuneSystemScanner

        scanner = ImmuneSystemScanner()
        result = scanner.scan_code("")

        # Empty code should be safe
        assert result["safe"] is True

    def test_scan_safe_code(self):
        """Test that safe code passes scanning."""
        from backend.core.immune_system import ImmuneSystemScanner

        scanner = ImmuneSystemScanner()
        safe_code = """
def calculate_sum(a, b):
    return a + b

def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        result = scanner.scan_code(safe_code)

        assert result["safe"] is True

    def test_scan_blocked_imports(self):
        """Test that blocked imports are detected."""
        from backend.core.immune_system import ImmuneSystemScanner

        scanner = ImmuneSystemScanner()

        # Test each blocked module
        blocked_modules = ["subprocess", "os", "sys", "socket", "pickle"]

        for module in blocked_modules:
            dangerous_code = f"import {module}"
            result = scanner.scan_code(dangerous_code)

            if module in ["subprocess", "os", "sys", "socket"]:
                assert result["safe"] is False

    def test_scan_dangerous_attribute_access(self):
        """Test detection of dangerous attribute access."""
        from backend.core.immune_system import ImmuneSystemScanner

        scanner = ImmuneSystemScanner()
        dangerous_code = """
import os
dangerous = os.system("whoami")
"""
        result = scanner.scan_code(dangerous_code)

        assert result["safe"] is False
        assert len(result["error"]) > 0

    def test_scan_eval_usage(self):
        """Test that eval usage is detected as dangerous."""
        from backend.core.immune_system import ImmuneSystemScanner

        scanner = ImmuneSystemScanner()
        dangerous_code = "result = eval(user_input)"

        result = scanner.scan_code(dangerous_code)

        assert result["safe"] is False

    def test_scan_exec_usage(self):
        """Test that exec usage is detected as dangerous."""
        from backend.core.immune_system import ImmuneSystemScanner

        scanner = ImmuneSystemScanner()
        dangerous_code = "exec(malicious_code)"

        result = scanner.scan_code(dangerous_code)

        assert result["safe"] is False


class TestASTSecurityScanner:
    """Test AST-based security scanner for code injection prevention."""

    def test_scanner_has_banned_imports(self):
        """Test that scanner has banned imports list."""
        from backend.core.immune_system import ASTSecurityScanner

        scanner = ASTSecurityScanner()
        assert hasattr(scanner, 'banned_imports')
        assert "os" in scanner.banned_imports
        assert "subprocess" in scanner.banned_imports

    def test_scanner_has_banned_functions(self):
        """Test that scanner has banned functions list."""
        from backend.core.immune_system import ASTSecurityScanner

        scanner = ASTSecurityScanner()
        assert hasattr(scanner, 'banned_functions')
        assert "eval" in scanner.banned_functions
        assert "exec" in scanner.banned_functions

    def test_scanner_has_banned_attributes(self):
        """Test that scanner has banned attributes list."""
        from backend.core.immune_system import ASTSecurityScanner

        scanner = ASTSecurityScanner()
        assert hasattr(scanner, 'banned_attributes')
        assert "__class__" in scanner.banned_attributes
        assert "__builtins__" in scanner.banned_attributes


class TestSecuritySandboxError:
    """Test security sandbox error exception."""

    def test_security_sandbox_error_exists(self):
        """Test that SecuritySandboxError exists."""
        from backend.core.immune_system import SecuritySandboxError

        assert SecuritySandboxError is not None

    def test_security_sandbox_error_is_exception(self):
        """Test that SecuritySandboxError is an Exception subclass."""
        from backend.core.immune_system import SecuritySandboxError

        assert issubclass(SecuritySandboxError, Exception)
