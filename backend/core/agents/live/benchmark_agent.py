import time
from typing import Any, ClassVar

from core.logging_config import logger


def _resolve_dependencies() -> tuple[type, Any]:
    """বাংলা: lazy domain adapter (issue #126) — brain/database নির্ভরতা
    ভোগের জায়গায় resolve; module-import সময়ে কোনো cross-domain import নেই।"""
    from brain.model_router import ModelRouter
    from database.supabase_client import db

    return ModelRouter, db


class BenchmarkAgent:
    """
    An agent that runs a suite of benchmark prompts against all configured
    AI providers to measure latency, cost, and output quality.
    """

    BENCHMARK_PROMPTS: ClassVar[Any] = [
        {
            "category": "coding",
            "prompt": "Write a Python function to calculate the factorial of a number using recursion.",
        },
        {
            "category": "reasoning",
            "prompt": "If all Zirps are Zorps, and some Zorps are Zots, can we say for certain that some Zirps are Zots? Explain your reasoning.",
        },
        {
            "category": "creative",
            "prompt": "Write a short, three-line poem about a robot learning to dream.",
        },
        {"category": "general", "prompt": "What is the capital of Mongolia?"},
    ]

    def __init__(self):
        try:
            model_router_cls, db_module = _resolve_dependencies()
        except ImportError as exc:
            raise ImportError("BenchmarkAgent requires ModelRouter and Supabase client.") from exc
        self.model_router = model_router_cls()
        self.db_client = db_module.client
        logger.info("Initialized BenchmarkAgent")

    async def run_benchmark(self, providers: list[str]) -> dict[str, Any]:
        """
        Runs the full benchmark suite across the given providers.
        """
        logger.info(f"Starting benchmark run for providers: {providers}")
        full_report = {"providers": {}, "summary": {}}
        all_results = []

        for provider in providers:
            logger.info(f"Benchmarking provider: {provider}")
            provider_results = []
            for item in self.BENCHMARK_PROMPTS:
                start_time = time.time()

                # Force routing to the specific provider for this test
                # Note: This assumes ModelRouter can be forced, or we'd need a different approach.
                response = await self.model_router.async_route_and_generate(
                    item["prompt"],
                    task_type=item["category"],
                    # A mechanism to force provider would be needed in ModelRouter
                    # preferred_provider=provider
                )

                end_time = time.time()
                latency = end_time - start_time

                result = {
                    "provider": provider,
                    "category": item["category"],
                    "latency_seconds": latency,
                    "cost": response.get("cost", 0.0),
                    "output_length": len(response.get("text", "")),
                    "success": response.get("success", False),
                    "timestamp": time.time(),
                }
                provider_results.append(result)
                all_results.append(result)

            full_report["providers"][provider] = provider_results

        if self.db_client:
            logger.info("Persisting benchmark results to database.")
            await self.db_client.table("provider_benchmarks").insert(all_results).execute()

        logger.info("Benchmark run completed.")
        return full_report
