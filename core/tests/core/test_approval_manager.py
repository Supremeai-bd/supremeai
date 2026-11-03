"""Approval Manager tests for SupremeAI 2.0.

বাংলা: `api/routes/approval_manager.py`-এর SKILL_GENERATION অনুমোদন পথের জন্য
টেস্ট। এই ফাইলটা যোগ করা হয়েছে একটা রিয়েল বাগের রিগ্রেশন-টেস্ট হিসেবে:
আগে এই কোড `CodeValidator` (কখনো import না-হওয়া, এবং ওই মেথডও নেই এমন একটা
ক্লাস) ব্যবহার করতো, ফলে প্রতিটা SKILL_GENERATION approval অ্যাটেম্পট
NameError-এ ক্র্যাশ করতো। ফিক্সের পর এখন সঠিক ক্লাস (`AICodeValidator`) এবং
সহজ সরল return-key (`can_use`) ব্যবহার হয় — নিচের টেস্টগুলো নিশ্চিত করে যে:
  ১) ভ্যালিড কোড approve হলে সত্যিই ফাইল লেখা হয় ও কোনো ব্যতিক্রম ছাড়াই সফল হয়
  ২) অকার্যকর/সিনট্যাক্স-ভুল কোড approve করতে গেলে পরিষ্কার 400 আসে, 500/NameError না
"""

import os
import uuid

import pytest
from fastapi import HTTPException


@pytest.fixture
def clean_skills_dir():
    """টেস্টের সময় লেখা কোনো স্কিল ফাইল টেস্ট শেষে পরিষ্কার করে দেয়।"""
    from api.routes.approval_manager import _get_allowed_skills_dir

    skills_dir = _get_allowed_skills_dir()
    os.makedirs(skills_dir, exist_ok=True)
    written_paths: list[str] = []
    yield written_paths
    for p in written_paths:
        if os.path.exists(p):
            os.remove(p)


def _make_skill_generation_task(skill_name: str, code: str):
    """একটা PENDING SKILL_GENERATION টাস্ক sqlite-backed store-এ তৈরি করে।"""
    from models.pending_tasks import TaskType, create_pending_task

    return create_pending_task(
        task_type=TaskType.SKILL_GENERATION,
        payload={"skill_name": skill_name, "generated_code": code},
    )


class TestApproveSkillGeneration:
    """Regression tests: previously always crashed (NameError) before
    even reaching validation, because CodeValidator was never imported."""

    def test_valid_code_is_approved_and_written(self, clean_skills_dir):
        """সিনট্যাক্টিকালি সঠিক কোড approve হলে ফাইল সত্যিই লেখা হবে, exception ছাড়া।"""
        from api.routes.approval_manager import (
            ApproveRequest,
            _get_allowed_skills_dir,
            approve_task,
        )

        skill_name = f"test_skill_{uuid.uuid4().hex[:8]}"
        code = "def run():\n    return 'ok'\n"
        task = _make_skill_generation_task(skill_name, code)

        result = approve_task(
            task.task_id,
            ApproveRequest(resolved_by="tester", reason="unit-test"),
            _={"role": "admin"},
        )

        assert result["status"] == "approved"
        written_path = os.path.join(_get_allowed_skills_dir(), f"{skill_name}.py")
        clean_skills_dir.append(written_path)
        assert os.path.exists(written_path)
        with open(written_path, encoding="utf-8") as f:
            assert f.read() == code

    def test_syntactically_invalid_code_returns_400_not_500(self):
        """ভুল সিনট্যাক্সের কোড 400 দেবে ('Code validation failed'), NameError/500 না।"""
        from api.routes.approval_manager import ApproveRequest, approve_task

        skill_name = f"test_bad_skill_{uuid.uuid4().hex[:8]}"
        code = "def run(:\n    return\n"  # ইচ্ছাকৃত সিনট্যাক্স এরর
        task = _make_skill_generation_task(skill_name, code)

        with pytest.raises(HTTPException) as exc_info:
            approve_task(
                task.task_id,
                ApproveRequest(resolved_by="tester", reason="unit-test"),
                _={"role": "admin"},
            )

        assert exc_info.value.status_code == 400
        assert "Code validation failed" in exc_info.value.detail

    def test_missing_skill_name_returns_400(self):
        """skill_name অনুপস্থিত থাকলে 400 (Missing skill_name...)।"""
        from api.routes.approval_manager import ApproveRequest, approve_task

        task = _make_skill_generation_task("", "print('hi')")

        with pytest.raises(HTTPException) as exc_info:
            approve_task(
                task.task_id,
                ApproveRequest(resolved_by="tester", reason="unit-test"),
                _={"role": "admin"},
            )

        assert exc_info.value.status_code == 400

    def test_path_traversal_skill_name_blocked(self):
        """স্কিল নেমে path-traversal ক্যারেক্টার থাকলে অনুমোদনের আগেই 400 দিয়ে আটকাবে।"""
        from api.routes.approval_manager import ApproveRequest, approve_task

        task = _make_skill_generation_task("../../etc/passwd", "print('hi')")

        with pytest.raises(HTTPException) as exc_info:
            approve_task(
                task.task_id,
                ApproveRequest(resolved_by="tester", reason="unit-test"),
                _={"role": "admin"},
            )

        assert exc_info.value.status_code == 400


class TestAICodeValidatorIntegration:
    """সরাসরি AICodeValidator-এর সাথে approval_manager-এর ইন্টিগ্রেশন যাচাই —
    নিশ্চিত করে যে ব্যবহৃত return-key ('can_use') বাস্তবে ক্লাসটার সাথে মেলে।"""

    def test_validator_class_is_importable_and_has_expected_api(self):
        from core.code_validator import AICodeValidator

        validator = AICodeValidator()
        result = validator.validate_before_use("def run():\n    return 1\n")
        assert "can_use" in result
        assert result["can_use"] is True

    def test_validator_flags_undefined_variable(self):
        from core.code_validator import AICodeValidator

        validator = AICodeValidator()
        result = validator.validate_before_use("def run():\n    return some_undefined_name\n")
        assert result["can_use"] is False
