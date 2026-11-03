import pytest_asyncio


@pytest_asyncio.fixture(scope="session")
async def override_setup_test_database():
    yield
