import asyncio

import pytest

from core.memory_manager import FreeTierMemoryManager


@pytest.mark.asyncio
async def test_aggressive_cleanup_does_not_raise():
    manager = FreeTierMemoryManager()

    try:
        # Force aggressive cleanup
        await manager._aggressive_cleanup(force=True)
    except Exception as e:
        pytest.fail(f"_aggressive_cleanup raised an exception unexpectedly: {e}")
