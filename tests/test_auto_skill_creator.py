from __future__ import annotations

import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch
from evolution.auto_skill_creator import AutoSkillCreator


def _make_creator(rules_engine=None, skills_dir=None):
    creator = AutoSkillCreator(rules_engine=rules_engine)
    if skills_dir is None:
        skills_dir = tempfile.mkdtemp()
    creator.skills_dir = skills_dir
    return creator, skills_dir


def test_generate_skill_code_basic():
    creator, _ = _make_creator()
    code = creator.generate_skill_code("my_skill")
    assert "class MySkill:" in code
    assert 'self.name = "my_skill"' in code
    assert "def run(self, payload: dict) -> dict:" in code
    assert "'my_skill'" in code


def test_generate_skill_code_special_chars():
    creator, _ = _make_creator()
    code = creator.generate_skill_code("auto_data_processor")
    assert "class AutoDataProcessor:" in code


def test_analyze_demand_patterns_from_rules():
    mock_rules = MagicMock()
    mock_rules.rules = {
        "patterns": {
            "repeated_tasks": ["send_email", "process_invoice"]
        }
    }
    creator, _ = _make_creator(rules_engine=mock_rules)
    task_history = []
    patterns = creator.analyze_demand_patterns(task_history)
    assert "send_email" in patterns
    assert "process_invoice" in patterns


def test_analyze_demand_patterns_from_failures():
    creator, _ = _make_creator()
    task_history = [
        {"success": False, "task": "failed_task_a"},
        {"success": False, "task": "failed_task_a"},
        {"success": True, "task": "ok_task"},
        {"success": False, "task": "failed_task_b"},
    ]
    patterns = creator.analyze_demand_patterns(task_history)
    assert "failed_task_a" in patterns
    assert "failed_task_b" in patterns
    assert len(patterns) == 2


def test_analyze_demand_patterns_no_engine_no_failures():
    creator, _ = _make_creator(rules_engine=None)
    task_history = [{"success": True, "task": "ok_task"}]
    patterns = creator.analyze_demand_patterns(task_history)
    assert patterns == []


def test_analyze_demand_patterns_deduplicates():
    mock_rules = MagicMock()
    mock_rules.rules = {
        "patterns": {
            "repeated_tasks": ["send_email", "send_email"]
        }
    }
    creator, _ = _make_creator(rules_engine=mock_rules)
    patterns = creator.analyze_demand_patterns([])
    assert patterns == ["send_email"]


def test_register_new_skill_with_generated_code():
    creator, skills_dir = _make_creator()
    skill = {
        "skill_name": "test_skill",
        "generated_code": 'class TestSkill:\n    def run(self, payload): pass\n',
    }
    result = creator.register_new_skill(skill)
    assert result["skill_name"] == "test_skill"
    assert result["status"] == "registered"
    assert result["filenae"] == "test_skill.py"
    path = result["path"]
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "class TestSkill:" in content


def test_register_new_skill_generates_code_when_missing():
    creator, skills_dir = _make_creator()
    skill = {"skill_name": "gen_skill"}
    result = creator.register_new_skill(skill)
    assert result["status"] == "registered"
    assert os.path.exists(result["path"])
    assert "class GenSkill:" in open(result["path"], "r", encoding="utf-8").read()


def test_register_new_skill_creates_directory():
    creator, skills_dir = _make_creator()
    nested = os.path.join(skills_dir, "sub", "dir")
    creator.skills_dir = nested
    skill = {"skill_name": "dir_skill"}
    result = creator.register_new_skill(skill)
    assert os.path.isdir(nested)
    assert os.path.exists(result["path"])


def test_test_new_skill_passes_valid_code():
    creator, _ = _make_creator()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("class GoodSkill:\n    def run(self, payload): return {}\n")
        path = f.name
    try:
        result = creator.test_new_skill(path)
        assert result["passed"] is True
        assert result["skill_path"] == path
    finally:
        os.unlink(path)


def test_test_new_skill_fails_syntax_error():
    creator, _ = _make_creator()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("class BadSkill:\n    def run(self, payload):\n        return }\n")
        path = f.name
    try:
        result = creator.test_new_skill(path)
        assert result["passed"] is False
        assert "reason" in result
    finally:
        os.unlink(path)


def test_test_new_skill_file_not_found():
    creator, _ = _make_creator()
    result = creator.test_new_skill("/nonexistent/path/skill.py")
    assert result["passed"] is False
    assert "file not found" in result["reason"]


@patch("evolution.auto_skill_creator.subprocess.run")
def test_test_new_skill_subprocess_timeout(mock_run):
    creator, _ = _make_creator()
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python"], timeout=30)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("class Skill:\n    pass\n")
        path = f.name
    try:
        result = creator.test_new_skill(path)
        assert result["passed"] is False
        assert len(result["reason"]) > 0
    finally:
        os.unlink(path)


def test_generate_from_failures_creates_skills():
    creator, skills_dir = _make_creator()
    task_history = [
        {"success": False, "task": "failed_email_task"},
        {"success": False, "task": "failed_invoice_task"},
    ]
    created = creator.generate_from_failures(task_history)
    assert len(created) == 2
    names = [c["skill_name"] for c in created]
    assert "auto_failed_email_task" in names
    assert "auto_failed_invoice_task" in names
    for c in created:
        assert os.path.exists(c["path"])
        assert "test_passed" in c


def test_generate_from_failures_empty_history():
    creator, _ = _make_creator()
    created = creator.generate_from_failures([])
    assert created == []


def test_generate_from_failures_all_success():
    creator, _ = _make_creator()
    task_history = [
        {"success": True, "task": "ok_task"},
        {"success": True, "task": "ok_task2"},
    ]
    created = creator.generate_from_failures(task_history)
    assert created == []


def test_register_new_skill_iso_timestamp_format():
    creator, skills_dir = _make_creator()
    skill = {"skill_name": "time_skill"}
    result = creator.register_new_skill(skill)
    assert "registered_at" in result
    assert "T" in result["registered_at"] or "Z" in result["registered_at"]