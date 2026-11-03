"""
Tests for core/code_validator.py — AICodeValidator & CodeValidator
"""

from __future__ import annotations

import pytest

from core.code_validator import AICodeValidator, CodeValidator


class TestAICodeValidator:
    @pytest.fixture
    def validator(self):
        return AICodeValidator()

    def test_valid_syntax(self, validator):
        code = "x = 1\nprint(x)"
        result = validator.validate_before_use(code)
        assert result["checks"]["syntax_valid"] is True
        assert result["checks"]["indentation_correct"] is True

    def test_invalid_syntax(self, validator):
        code = "x = 1\n    print(x)"  # Unexpected indent
        result = validator.validate_before_use(code)
        assert result["checks"]["syntax_valid"] is False

    def test_no_hallucinated_imports(self, validator):
        code = "import os\nprint('hello')"
        result = validator.validate_before_use(code)
        assert result["checks"]["no_hallucinated_imports"] is True

    def test_hallucinated_import(self, validator):
        code = "import nonexistent_module_xyz\nprint('hello')"
        result = validator.validate_before_use(code)
        assert result["checks"]["no_hallucinated_imports"] is False

    def test_no_undefined_variables(self, validator):
        code = "x = 1\nprint(x)"
        result = validator.validate_before_use(code)
        assert result["checks"]["no_undefined_variables"] is True

    def test_undefined_variables(self, validator):
        code = "print(undefined_var)"
        result = validator.validate_before_use(code)
        assert result["checks"]["no_undefined_variables"] is False

    def test_no_infinite_loops(self, validator):
        code = "for i in range(10):\n    print(i)"
        result = validator.validate_before_use(code)
        assert result["checks"]["no_infinite_loops"] is True

    def test_infinite_loop_detected(self, validator):
        code = "while True:\n    pass"
        result = validator.validate_before_use(code)
        assert result["checks"]["no_infinite_loops"] is False

    def test_while_true_with_break_is_safe(self, validator):
        code = "while True:\n    if condition:\n        break"
        result = validator.validate_before_use(code)
        assert result["checks"]["no_infinite_loops"] is True

    def test_auto_fix_missing_colon(self, validator):
        code = "def my_func()\n    pass"
        result = validator.validate_before_use(code)
        assert result["checks"]["syntax_valid"] is True or "fixed_code" in result

    def test_all_checks_pass_for_valid_code(self, validator):
        code = "def add(a, b):\n    return a + b\n\nresult = add(1, 2)\nprint(result)"
        result = validator.validate_before_use(code)
        assert result["can_use"] is True

    def test_empty_code(self, validator):
        result = validator.validate_before_use("")
        assert result["can_use"] is True

    def test_code_with_class_definition(self, validator):
        code = "class MyClass:\n    def __init__(self):\n        self.value = 42"
        result = validator.validate_before_use(code)
        assert result["can_use"] is True

    def test_code_with_async_function(self, validator):
        code = "async def fetch_data():\n    return await some_async_func()"
        result = validator.validate_before_use(code)
        assert result["can_use"] is True


class TestCodeValidator:
    @pytest.fixture
    def validator(self):
        return CodeValidator()

    def test_validate_syntax_valid(self, validator):
        result = validator.validate_syntax("print('hello')")
        assert result.get("valid") is True

    def test_validate_syntax_invalid(self, validator):
        result = validator.validate_syntax("print('hello'")
        assert result.get("valid") is False

    def test_validate_path_exists(self, validator, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        result = validator.validate_path(str(test_file))
        assert result.get("exists") is True

    def test_validate_path_not_exists(self, validator):
        result = validator.validate_path("/nonexistent/path/file.txt")
        assert result.get("exists") is False

    def test_validate_url_valid(self, validator):
        result = validator.validate_url("https://example.com")
        assert result.get("valid") is True

    def test_validate_url_invalid(self, validator):
        result = validator.validate_url("not-a-url")
        assert result.get("valid") is False

    def test_validate_url_empty(self, validator):
        result = validator.validate_url("")
        assert result.get("valid") is False

    def test_validate_text_with_code_blocks(self, validator):
        text = "Here is some code:\n```python\nprint('hello')\n```"
        result = validator.validate(text)
        assert isinstance(result, dict)
