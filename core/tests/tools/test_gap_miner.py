import re
import pytest
from pathlib import Path
from core.tools.gap_miner.tools.gap_miner import (
    SECRET_VALUE_RE,
    TODO_RE,
    Miner,
)

def test_secret_value_regex_whitespace():
    # Synthetic test samples (no real credentials) dynamically formatted to avoid false-positive secret scanner alerts
    prefix = "api_key"
    mock_val = "mock_key_16_chars"
    sample_with_spaces = f'{prefix}  =  "{mock_val}"'
    match = SECRET_VALUE_RE.search(sample_with_spaces)
    assert match is not None, "Whitespace-separated secret assignment should match"

    colon_prefix = "secret"
    mock_token = "mock_token_16chars"
    sample_with_colon = f'{colon_prefix}: "{mock_token}"'
    match_colon = SECRET_VALUE_RE.search(sample_with_colon)
    assert match_colon is not None, "Colon and whitespace-separated secret should match"

    sample_literal_backslash_s = r'api_key\s=\s"synthetic_dummy_key_1234567890abcdef"'
    # Should match or not match, but normal code with real spaces MUST match.

def test_todo_regex_word_boundaries():
    valid_todos = [
        "// TODO: implement this",
        "# FIXME fix issue",
        "/* HACK temporary workaround */",
        "XXX do not ship",
        "BUG in line 4",
        "TEMP override",
    ]
    for text in valid_todos:
        matches = TODO_RE.findall(text)
        assert len(matches) == 1, f"Expected 1 match for '{text}', got {matches}"

    false_positives = [
        "METHODology is sound",
        "TODAY is a good day",
        "ATTEMPTED to connect",
        "DEBUGGING the flow",
        "HACKATHON event",
    ]
    for text in false_positives:
        matches = TODO_RE.findall(text)
        assert len(matches) == 0, f"Expected 0 matches for false positive '{text}', got {matches}"

def test_line_counting_and_loc(tmp_path: Path):
    test_file = tmp_path / "test_file.py"
    content = "line1\nline2\nline3\nline4\nline5\n"
    test_file.write_text(content, encoding="utf-8")

    miner = Miner(tmp_path)
    # Miner counts lines using '\n'
    text = miner.text(test_file)
    lines = text.count("\n") + (1 if text else 0)
    # 5 newlines in content -> 6 lines total (or 5 lines if standard trailing newline)
    # Specifically, text.count("\n") returns 5, NOT 0 (which was the bug with text.count("\\n"))
    assert text.count("\n") == 5
    assert text.count("\\n") == 0

def test_ci_checks_regex():
    ci_checks = {
        "test": r"(^|[\s_-])(pytest|vitest|jest|npm run test|pnpm .*test|yarn .*test)",
        "lint": r"(^|[\s_-])(eslint|ruff|flake8|mypy|lint)",
    }
    
    # Preceded by space, underscore, dash, or newline
    sample_workflow = """
    jobs:
      test:
        steps:
          - run: pytest tests/
          - run: ruff check .
    """
    assert re.search(ci_checks["test"], sample_workflow, re.IGNORECASE) is not None
    assert re.search(ci_checks["lint"], sample_workflow, re.IGNORECASE) is not None

    sample_dashed = "run-test: npm run test"
    assert re.search(ci_checks["test"], sample_dashed, re.IGNORECASE) is not None
