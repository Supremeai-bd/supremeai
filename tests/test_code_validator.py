import os

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest
from unittest.mock import patch


@pytest.fixture
def validator():
    from core.code_validator import CodeValidator
    return CodeValidator()


class TestAICodeValidator:
    @pytest.fixture
    def ai(self):
        from core.code_validator import AICodeValidator
        return AICodeValidator()

    @pytest.mark.parametrize("code", [
        "x = 1",
        "def foo():\n    return 1",
        "for i in range(10):\n    print(i)",
    ])
    def test_valid_code_passes(self, ai, code):
        res = ai.validate_before_use(code)
        assert res["can_use"] is True

    def test_syntax_error_detected(self, ai):
        res = ai.validate_before_use("def foo(\n    pass")
        assert res["checks"]["syntax_valid"] is False

    def test_infinite_while_true_detected(self, ai):
        res = ai.validate_before_use("while True:\n    x = 1")
        assert res["checks"]["no_infinite_loops"] is False

    def test_while_true_with_break_safe(self, ai):
        code = "while True:\n    break"
        res = ai.validate_before_use(code)
        assert res["checks"]["no_infinite_loops"] is True

    def test_undefined_variable_detected(self, ai):
        res = ai.validate_before_use("print(undefined_var)")
        assert res["checks"]["no_undefined_variables"] is False

    def test_defined_function_and_call_safe(self, ai):
        code = "def foo():\n    return 1\n\nprint(foo())"
        res = ai.validate_before_use(code)
        assert res["checks"]["no_undefined_variables"] is True


class TestCodeValidator:
    def test_validate_syntax_non_python(self, validator):
        res = validator.validate_syntax("console.log(1)", "javascript")
        assert res["is_valid"] is True

    def test_validate_syntax_python_valid(self, validator):
        res = validator.validate_syntax("x = 1", "python")
        assert res["is_valid"] is True
        assert res["errors"] == []

    def test_validate_syntax_python_invalid(self, validator):
        res = validator.validate_syntax("def foo(\n    pass", "python")
        assert res["is_valid"] is False

    def test_validate_url_valid(self, validator):
        res = validator.validate_url("https://example.com/path")
        assert res["is_valid"] is True

    def test_validate_url_disallowed_domain(self, validator):
        res = validator.validate_url("https://github.com/nadim9/supremeai")
        assert res["is_valid"] is False

    def test_validate_path_existing_file(self, validator, tmp_path):
        f = tmp_path / "f.py"
        f.write_text("x=1")
        res = validator.validate_path(str(f))
        assert res["exists"] is True
        assert res["is_file"] is True

    def test_validate_path_missing(self, validator):
        res = validator.validate_path("/nonexistent/path/xyz.py")
        assert res["exists"] is False

    @patch("core.code_validator.re.findall")
    def test_validate_text_with_blocked_url(self, mock_find, validator):
        mock_find.side_effect = lambda p, t, f=None: (
            ["https://github.com/nadim9/supremeai"] if "https?://" in p else []
        )
        res = validator.validate("see https://github.com/nadim9/supremeai")
        assert res["is_valid"] is False
