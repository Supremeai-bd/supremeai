import asyncio
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

# Enable Chaos Mode manually for this test script
os.environ["ENABLE_CHAOS_MODE"] = "True"

from core.maintenance_pipeline import maintenance_pipeline

async def test_chaos_and_recovery():
    print("Starting Chaos & Recovery Test...")

    # 1. Manually force the health check which includes Chaos Probes
    print("Simulating Chaos via Health Probes...")

    # Run the health check a few times to increase the 5% chance of chaos
    for i in range(20):
        results = await maintenance_pipeline.run_health_check()
        if maintenance_pipeline.health_score < 100:
            print(f"Health Dropped! Score: {maintenance_pipeline.health_score}")
            print(f"Results: {results}")
            break
        await asyncio.sleep(0.1)

    print(f"Current Health Score: {maintenance_pipeline.health_score}")
    print("Test Completed.")

if __name__ == "__main__":
    asyncio.run(test_chaos_and_recovery())
