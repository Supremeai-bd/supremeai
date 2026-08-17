import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
root_env = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(root_env)

async def test_connection():
    """
    Test connectivity to the Neo4j database using credentials defined in .env.
    """
    # Import GraphService to test integration with settings config
    # We set PYTHONPATH to include backend/
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

    from tools.graph_service import GraphService

    logger.info("Starting Neo4j connectivity check...")

    # Instantiate GraphService (this reads from settings)
    graph_service = GraphService()

    if graph_service.dry_run:
        logger.error(
            "GraphService is running in DRY_RUN mode. "
            "Please check if 'NEO4J_PASSWORD' is set in your .env file."
        )
        return False

    try:
        # Simple query to verify connectivity
        async with graph_service.driver.session() as session:
            logger.info(f"Connecting to Neo4j URI: {graph_service.uri}...")
            result = await session.run("RETURN 1 AS num")
            single_result = await result.single()
            if single_result and single_result["num"] == 1:
                logger.info("✅ SUCCESS: Successfully connected to Neo4j instance!")
                return True
            else:
                logger.error("❌ FAILURE: Connection test query returned unexpected result.")
                return False
    except Exception as e:
        logger.error(f"❌ FAILURE: Failed to connect to Neo4j database. Error: {e}")
        return False
    finally:
        await graph_service.close()

if __name__ == "__main__":
    asyncio.run(test_connection())
