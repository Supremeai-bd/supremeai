import enum

import pytest

from core.enum_guard import EnumGuard, EnumGuardError


class MockStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


def test_enum_guard_success_parse():
    """নিশ্চিত করে যে সঠিক স্ট্রিং দিলে তা সঠিকভাবে এনাম অবজেক্টে কনভার্ট হয়।"""
    result = EnumGuard.validate_and_parse(MockStatus, "success", context="Test Pipeline")
    assert result == MockStatus.SUCCESS


def test_enum_guard_explosive_exception():
    """🛡️ সাইলেন্ট ফেইলর গার্ড: ইনভ্যালিড এনাম ভ্যালু দিলে যেন সাইলেন্টলি পাস না হয়ে এক্সেপশন রেইজ হয়।"""
    with pytest.raises(EnumGuardError) as exc_info:
        EnumGuard.validate_and_parse(MockStatus, "INVALID_STATE_MATRIX", context="Test Pipeline")

    assert "Invalid enum value" in str(exc_info.value)


def test_enum_guard_safe_fallback():
    """নিশ্চিত করে যে এক্সপেক্টেড ফলব্যাক মেকানিজম সঠিকভাবে কাজ করছে।"""
    result = EnumGuard.safe_fallback(
        MockStatus,
        "CORRUPTED_DATA",
        fallback=MockStatus.FAILED,
        context="Test Fallback",
    )
    assert result == MockStatus.FAILED
