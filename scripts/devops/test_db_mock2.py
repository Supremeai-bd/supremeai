import asyncio
from unittest.mock import patch, AsyncMock
from core.health_check import ComprehensiveHealthChecker, HealthStatus

async def main():
    checker = ComprehensiveHealthChecker()
    mock_engine = AsyncMock()
    mock_conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn
    
    with patch("database.session.init_engine"), \
         patch("database.session._engine_instance", mock_engine):
        result = await checker.check_database()
        print(f"Status: {result.status}")
        print(f"Message: {result.message}")

asyncio.run(main())
