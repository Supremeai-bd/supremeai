"""Tests for core.user_profiler — user classification + history update (graceful on missing brain)."""

import pytest

from core.user_profiler import UserMode, UserProfile, UserProfiler


@pytest.mark.asyncio
async def test_classify_user_returns_profile():
    prof = await UserProfiler().classify_user("user-42")
    assert isinstance(prof, UserProfile)
    assert prof.user_id == "user-42"
    assert prof.mode == UserMode.FAST_TRACK


@pytest.mark.asyncio
async def test_update_from_history_silences_import_error():
    # brain.user_digital_twin is not available in the light test env, so the
    # except branch (silenced logging) should be exercised without raising.
    await UserProfiler().update_from_history("u1", {"type": "question", "content": "hi"})
    # Reaching here means the exception was silenced.


def test_user_mode_values():
    assert UserMode.FAST_TRACK.value == "FAST_TRACK"
    assert UserMode.LEARNING.value == "LEARNING"
    assert UserMode.PRODUCTION.value == "PRODUCTION"


def test_user_profiler_modes_list():
    assert set(UserProfiler.MODES) == {"FAST_TRACK", "LEARNING", "PRODUCTION"}
