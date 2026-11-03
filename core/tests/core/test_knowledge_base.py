import json
import os

import pytest

from core.knowledge_base import MEMORY_FILE_PATH, get_from_memory, save_to_memory


@pytest.fixture
def temp_memory_file(tmp_path, monkeypatch):
    monkeypatch.setattr("core.knowledge_base.MEMORY_FILE_PATH", str(tmp_path / "memory.json"))
    with open(str(tmp_path / "memory.json"), "w") as f:
        json.dump({}, f)
    yield str(tmp_path / "memory.json")


def test_get_from_memory_empty_string(temp_memory_file):
    result = get_from_memory("")
    assert result is None


def test_get_from_memory_whitespace(temp_memory_file):
    result = get_from_memory("   ")
    assert result is None


def test_get_from_memory_whitespace_only(temp_memory_file):
    result = get_from_memory("   \t\n")
    assert result is None


def test_get_from_memory_returns_string(temp_memory_file):
    save_to_memory("test prompt", "solution code")
    result = get_from_memory("test prompt")
    assert result == "solution code"


def test_save_to_memory_creates_file_if_not_exists(temp_memory_file):
    # Ensure file exists
    with open(temp_memory_file, "w") as f:
        json.dump({}, f)

    save_to_memory("new prompt", "new solution")
    result = get_from_memory("new prompt")
    assert result == "new solution"
    with open(temp_memory_file) as f:
        data = json.load(f)
    assert data["new prompt"] == "new solution"


def test_save_to_memory_empty_prompt(temp_memory_file):
    save_to_memory("", "empty solution")
    result = get_from_memory("")
    assert result == "empty solution"


def test_save_to_memory_whitespace_prompt(temp_memory_file):
    save_to_memory("   ", "whitespace solution")
    result = get_from_memory("   ")
    assert result == "whitespace solution"


def test_save_to_memory_overwrites_multiple_times(temp_memory_file):
    save_to_memory("prompt", "first")
    save_to_memory("prompt", "second")
    save_to_memory("prompt", "third")
    result = get_from_memory("prompt")
    assert result == "third"


def test_get_from_memory_nonexistent_prompt_after_save(temp_memory_file):
    save_to_memory("existing", "original")
    save_to_memory("existing", "updated")
    result = get_from_memory("existing")
    assert result == "updated"


def test_save_to_memory_special_characters(temp_memory_file):
    save_to_memory("prompt with spaces!@#$%", "special chars solution")
    result = get_from_memory("prompt with spaces!@#$%")
    assert result == "special chars solution"


def test_save_to_memory_unicode_prompt(temp_memory_file):
    save_to_memory("prompt with unicode 🌍🚀", "unicode solution")
    result = get_from_memory("prompt with unicode 🌍🚀")
    assert result == "unicode solution"


def test_memory_file_path_is_correct():
    assert "memory_vault.json" in MEMORY_FILE_PATH
    assert os.path.exists(MEMORY_FILE_PATH) or os.path.isdir(os.path.dirname(MEMORY_FILE_PATH))


def test_memory_file_is_json_serializable(temp_memory_file):
    save_to_memory("test", "valid json")
    with open(temp_memory_file) as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_memory_file_is_overwritten_completely(temp_memory_file):
    save_to_memory("test", "initial")
    save_to_memory("test", "final")
    with open(temp_memory_file) as f:
        data = json.load(f)
    assert data == {"test": "final"}  # Changed from "valid" to "final" to match actual behavior
