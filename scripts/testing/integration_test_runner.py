#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SupremeAI 2.0 — Integration Test Runner
============================================================================
উদ্দেশ্য: End-to-End (E2E) integration tests চালায় — API, Database,
Message Queue, এবং External Services সব মিলিয়ে।

বৈশিষ্ট্য:
  - FastAPI TestClient + httpx AsyncClient
  - Firestore emulator / real instance support
  - Redis test container integration
  - Kafka / RabbitMQ message queue testing
  - JWT auth simulation
  - Multi-tenant isolation testing
  - Parallel test execution with pytest-xdist
  - HTML + JSON report generation

ব্যবহার:
  python scripts/testing/integration_test_runner.py
  python scripts/testing/integration_test_runner.py --env staging
  python scripts/testing/integration_test_runner.py --suite auth,api,payment
  python scripts/testing/integration_test_runner.py --parallel 4 --coverage

লেখক: SupremeAI Architecture Team
তারিখ: July 20, 2026
============================================================================
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from loguru import logger

# বাংলা মন্তব্য: sys.path হ্যাক এড়াতে ক্লিন ইমপোর্ট
try:
    from backend.core.config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from backend.core.config import settings


# ── Configuration ──────────────────────────────────────────────────────────
DEFAULT_ENV = os.getenv("TEST_ENV", "test")
DEFAULT_SUITE = os.getenv("TEST_SUITE", "all")
DEFAULT_PARALLEL = int(os.getenv("TEST_PARALLEL", "1"))
COVERAGE_ENABLED = os.getenv("TEST_COVERAGE", "false").lower() == "true"
REPORT_DIR = Path(os.getenv("TEST_REPORT_DIR", "tests/reports/integration"))
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
REDIS_TEST_URL = os.getenv("REDIS_TEST_URL", "redis://localhost:6379/15")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# ── Test Configuration Registry ──────────────────────────────────────────

@dataclass
class TestSuite:
    """বাংলা মন্তব্য: টেস্ট স্যুটের কনফিগারেশন"""
    name: str
    description: str
    test_files: list[str]
    fixtures: list[str]
    timeout: int = 300
    requires: list[str] = field(default_factory=list)  # services needed


TEST_SUITES: dict[str, TestSuite] = {
    "auth": TestSuite(
        name="auth",
        description="Authentication & Authorization E2E Tests",
        test_files=["tests/integration/test_auth.py"],
        fixtures=["auth_client", "test_user", "test_admin"],
        requires=["firestore", "redis"],
    ),
    "api": TestSuite(
        name="api",
        description="Core API End-to-End Tests",
        test_files=["tests/integration/test_api.py"],
        fixtures=["api_client", "test_tenant"],
        requires=["firestore", "redis", "api_server"],
    ),
    "llm": TestSuite(
        name="llm",
        description="LLM Gateway & Routing Tests",
        test_files=["tests/integration/test_llm.py"],
        fixtures=["llm_client", "mock_providers"],
        requires=["redis"],
    ),
    "payment": TestSuite(
        name="payment",
        description="Payment & Escrow Flow Tests",
        test_files=["tests/integration/test_payment.py"],
        fixtures=["payment_client", "test_payment_method"],
        requires=["firestore", "api_server"],
    ),
    "messaging": TestSuite(
        name="messaging",
        description="Event Bus & Message Queue Tests",
        test_files=["tests/integration/test_messaging.py"],
        fixtures=["event_bus", "redis_client"],
        requires=["redis", "kafka"],
    ),
    "security": TestSuite(
        name="security",
        description="Security & Compliance Tests",
        test_files=["tests/integration/test_security.py"],
        fixtures=["security_client", "guardian_ai"],
        requires=["firestore", "redis"],
    ),
    "multi_tenant": TestSuite(
        name="multi_tenant",
        description="Multi-tenant Isolation Tests",
        test_files=["tests/integration/test_multi_tenant.py"],
        fixtures=["tenant_a", "tenant_b", "api_client"],
        requires=["firestore", "redis"],
    ),
    "all": TestSuite(
        name="all",
        description="Complete Integration Test Suite",
        test_files=["tests/integration/"],
        fixtures=[],
        requires=["firestore", "redis", "api_server"],
    ),
}


# ── Service Health Checker ─────────────────────────────────────────────────

class ServiceHealthChecker:
    """
    বাংলা মন্তব্য: টেস্ট রান করার আগে সব ডিপেন্ডেন্সি সার্ভিসের হেলথ চেক করে।
    Firestore emulator, Redis, API server — সবকিছু রেডি কিনা তা নিশ্চিত করে।
    """

    def __init__(self):
        self.services: dict[str, bool] = {}

    async def check_firestore(self, emulator: bool = True) -> bool:
        """বাংলা মন্তব্য: Firestore connectivity check"""
        try:
            from google.cloud import firestore
            if emulator:
                os.environ["FIRESTORE_EMULATOR_HOST"] = FIRESTORE_EMULATOR_HOST
            client = firestore.Client(project="test-project")
            client.collection("_health_check").document("test").get()
            self.services["firestore"] = True
            logger.info("✅ Firestore connected")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Firestore unavailable: {e}")
            self.services["firestore"] = False
            return False

    async def check_redis(self) -> bool:
        """বাংলা মন্তব্য: Redis কানেকশন চেক করে"""
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(REDIS_TEST_URL)
            await client.ping()
            await client.close()
            self.services["redis"] = True
            logger.info("✅ Redis connected")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable: {e}")
            self.services["redis"] = False
            return False

    async def check_api_server(self) -> bool:
        """বাংলা মন্তব্য: API server রানিং কিনা চেক করে"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{API_BASE_URL}/health", timeout=5.0)
                healthy = response.status_code == 200
                self.services["api_server"] = healthy
                if healthy:
                    logger.info("✅ API server healthy")
                return healthy
        except Exception as e:
            logger.warning(f"⚠️ API server unavailable: {e}")
            self.services["api_server"] = False
            return False

    async def check_kafka(self) -> bool:
        """বাংলা মন্তব্য: Kafka broker কানেক্টিভিটি চেক (optional)"""
        try:
            from kafka import KafkaProducer
            producer = KafkaProducer(bootstrap_servers="localhost:9092",
                                     value_serializer=lambda v: json.dumps(v).encode())
            producer.close()
            self.services["kafka"] = True
            logger.info("✅ Kafka connected")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Kafka unavailable: {e}")
            self.services["kafka"] = False
            return False

    async def check_all(self, required: list[str]) -> dict[str, bool]:
        """বাংলা মন্তব্য: সব প্রয়োজনীয় সার্ভিস একসাথে চেক করে"""
        checks = {
            "firestore": self.check_firestore,
            "redis": self.check_redis,
            "api_server": self.check_api_server,
            "kafka": self.check_kafka,
        }

        for service in required:
            if service in checks:
                await checks[service]()

        return {k: v for k, v in self.services.items() if k in required}


# ── Test Environment Manager ───────────────────────────────────────────────

class TestEnvironmentManager:
    """
    বাংলা মন্তব্য: টেস্ট এনভায়রনমেন্ট সেটআপ ও টিয়ারডাউন ম্যানেজ করে।
    Docker compose, Firestore emulator, Redis container — সব ম্যানেজ করে।
    """

    def __init__(self, env: str = "test"):
        self.env = env
        self.processes: list[subprocess.Popen] = []
        self.temp_dirs: list[Path] = []

    async def setup(self) -> None:
        """বাংলা মন্তব্য: টেস্ট এনভায়রনমেন্ট সেটআপ করে"""
        logger.info(f"Setting up test environment: {self.env}")

        if self.env == "test":
            await self._start_firestore_emulator()
            await self._clear_redis_test_db()

        elif self.env == "staging":
            logger.info("Using staging environment — ensure services are running")

    async def teardown(self) -> None:
        """বাংলা মন্তব্য: টেস্ট এনভায়রনমেন্ট ক্লিনআপ করে"""
        logger.info("Tearing down test environment")

        for proc in self.processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        for temp_dir in self.temp_dirs:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _start_firestore_emulator(self) -> None:
        """বাংলা মন্তব্য: Firestore emulator স্টার্ট করে (যদি না চলে)"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", 8080))
            sock.close()

            if result != 0:  # Not running
                logger.info("Starting Firestore emulator...")
                proc = subprocess.Popen(
                    ["gcloud", "emulators", "firestore", "start", "--host-port=localhost:8080"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.processes.append(proc)
                await asyncio.sleep(3)  # Wait for startup
        except Exception as e:
            logger.warning(f"Could not start Firestore emulator: {e}")

    async def _clear_redis_test_db(self) -> None:
        """বাংলা মন্তব্য: Redis test database (DB 15) ক্লিয়ার করে"""
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(REDIS_TEST_URL)
            await client.flushdb()
            await client.close()
            logger.info("Redis test DB cleared")
        except Exception as e:
            logger.warning(f"Could not clear Redis: {e}")


# ── Test Executor ──────────────────────────────────────────────────────────

class TestExecutor:
    """
    বাংলা মন্তব্য: pytest দিয়ে টেস্ট এক্সিকিউট করে এবং রেজাল্ট কালেক্ট করে।
    Parallel execution, coverage, এবং custom reporting সাপোর্ট করে।
    """

    def __init__(self, suite: TestSuite, env: str, parallel: int, coverage: bool):
        self.suite = suite
        self.env = env
        self.parallel = parallel
        self.coverage = coverage
        self.results: dict[str, Any] = {}

    async def execute(self) -> dict[str, Any]:
        """বাংলা মন্তব্য: টেস্ট স্যুট এক্সিকিউট করে"""
        start_time = time.time()

        cmd = [sys.executable, "-m", "pytest"]

        for test_file in self.suite.test_files:
            cmd.append(test_file)

        cmd.extend([
            "-v",
            "--tb=short",
            f"--timeout={self.suite.timeout}",
        ])

        if self.parallel > 1:
            cmd.extend(["-n", str(self.parallel), "--dist", "loadgroup"])

        if self.coverage:
            cmd.extend([
                "--cov=backend",
                "--cov-report=term-missing",
                "--cov-report=html:tests/reports/coverage",
                "--cov-report=json:tests/reports/coverage.json",
            ])

        env = os.environ.copy()
        env["SUPREMEAI_TEST_ENV"] = self.env
        env["SUPREMEAI_TEST_SUITE"] = self.suite.name

        logger.info(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=self.suite.timeout + 60,
            )

            elapsed = time.time() - start_time

            self.results = {
                "suite": self.suite.name,
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "elapsed_time": elapsed,
                "parallel": self.parallel,
                "coverage": self._parse_coverage(),
            }

            return self.results

        except subprocess.TimeoutExpired:
            return {
                "suite": self.suite.name,
                "success": False,
                "error": f"Test suite timed out after {self.suite.timeout + 60}s",
                "elapsed_time": self.suite.timeout + 60,
            }

    def _parse_coverage(self) -> float:
        """বাংলা মন্তব্য: coverage.json থেকে কোভারেজ পার্স করে"""
        cov_file = Path("tests/reports/coverage.json")
        if cov_file.exists():
            try:
                data = json.loads(cov_file.read_text())
                return data.get("totals", {}).get("percent_covered", 0.0)
            except Exception as e:
                # বাংলা: coverage.json পার্স ব্যর্থ হলে চুপচাপ 0.0% না দেখিয়ে কারণ জানিয়ে দিন
                logger.warning(f"Failed to parse {cov_file}: {e}")
        return 0.0


# ── Report Generator ─────────────────────────────────────────────────────

class ReportGenerator:
    """
    বাংলা মন্তব্য: টেস্ট রেজাল্ট থেকে HTML এবং JSON রিপোর্ট জেনারেট করে।
    SupremeAI Dashboard-এ দেখানোর জন্য optimized।
    """

    def __init__(self, output_dir: Path = REPORT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html(self, results: dict[str, Any]) -> str:
        """বাংলা মন্তব্য: HTML রিপোর্ট জেনারেট করে"""
        suite = results.get("suite", "unknown")
        success = results.get("success", False)
        elapsed = results.get("elapsed_time", 0)
        coverage = results.get("coverage", 0)
        stdout = results.get("stdout", "")

        status_color = "#28a745" if success else "#dc3545"
        status_text = "PASSED" if success else "FAILED"

        html = f"""<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <title>SupremeAI Integration Test Report — {suite}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        .header {{ background: #161b22; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .status {{ display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; color: white; background: {status_color}; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #58a6ff; }}
        .metric-label {{ font-size: 12px; color: #8b949e; }}
        pre {{ background: #161b22; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 12px; }}
        .success {{ color: #3fb950; }} .failure {{ color: #f85149; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 SupremeAI Integration Test Report</h1>
        <span class="status">{status_text}</span>
        <div style="margin-top: 15px;">
            <div class="metric"><div class="metric-value">{suite}</div><div class="metric-label">SUITE</div></div>
            <div class="metric"><div class="metric-value">{elapsed:.2f}s</div><div class="metric-label">DURATION</div></div>
            <div class="metric"><div class="metric-value">{coverage:.1f}%</div><div class="metric-label">COVERAGE</div></div>
            <div class="metric"><div class="metric-value">{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}</div><div class="metric-label">TIMESTAMP</div></div>
        </div>
    </div>
    <h2>📋 Test Output</h2>
    <pre>{stdout}</pre>
</body>
</html>"""

        html_file = self.output_dir / f"report_{suite}_{datetime.now(UTC):%Y%m%d_%H%M%S}.html"
        html_file.write_text(html, encoding="utf-8")
        logger.info(f"HTML report saved: {html_file}")
        return str(html_file)

    def generate_json(self, results: dict[str, Any]) -> str:
        """বাংলা মন্তব্য: JSON রিপোর্ট জেনারেট করে — CI/CD pipeline-এ ব্যবহারের জন্য"""
        report = {
            "project": "SupremeAI 2.0",
            "report_type": "integration_test",
            "timestamp": datetime.now(UTC).isoformat(),
            "results": results,
        }

        json_file = self.output_dir / f"report_{results.get('suite', 'unknown')}_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
        json_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"JSON report saved: {json_file}")
        return str(json_file)

    def generate_summary(self, all_results: list[dict[str, Any]]) -> str:
        """বাংলা মন্তব্য: একাধিক স্যুটের জন্য সারসংক্ষেপ রিপোর্ট"""
        total = len(all_results)
        passed = sum(1 for r in all_results if r.get("success"))
        failed = total - passed
        avg_time = sum(r.get("elapsed_time", 0) for r in all_results) / total if total else 0
        avg_coverage = sum(r.get("coverage", 0) for r in all_results) / total if total else 0

        summary = f"""
╔══════════════════════════════════════════════════════════════╗
║         SupremeAI Integration Test Summary                  ║
╠══════════════════════════════════════════════════════════════╣
║  Total Suites : {total:>3}                                      ║
║  ✅ Passed    : {passed:>3}                                      ║
║  ❌ Failed    : {failed:>3}                                      ║
║  ⏱️  Avg Time   : {avg_time:>6.2f}s                                  ║
║  📊 Avg Coverage: {avg_coverage:>5.1f}%                                 ║
║  🕐 Timestamp  : {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'):>20}          ║
╚══════════════════════════════════════════════════════════════╝
"""
        print(summary)
        return summary


# ── Integration Test Runner (Main Class) ─────────────────────────────────

class IntegrationTestRunner:
    """
    বাংলা মন্তব্য: মূল অরকেস্ট্রেটর ক্লাস। সব কম্পোনেন্টকে একসাথে চালায়।
    """

    def __init__(self, env: str, parallel: int, coverage: bool):
        self.env = env
        self.parallel = parallel
        self.coverage = coverage
        self.env_manager = TestEnvironmentManager(env)
        self.health_checker = ServiceHealthChecker()
        self.report_generator = ReportGenerator()
        self.all_results: list[dict[str, Any]] = []

    async def run_suite(self, suite_name: str) -> dict[str, Any]:
        """বাংলা মন্তব্য: একক টেস্ট স্যুট রান করে"""
        if suite_name not in TEST_SUITES:
            logger.error(f"Unknown test suite: {suite_name}")
            return {"success": False, "error": f"Unknown suite: {suite_name}"}

        suite = TEST_SUITES[suite_name]
        logger.info(f"\n{'='*60}")
        logger.info(f"Running suite: {suite.name} — {suite.description}")
        logger.info(f"Requires: {', '.join(suite.requires)}")

        health = await self.health_checker.check_all(suite.requires)
        missing = [s for s, ok in health.items() if not ok]
        if missing:
            logger.error(f"Missing required services: {missing}")
            return {"success": False, "error": f"Missing services: {missing}"}

        executor = TestExecutor(suite, self.env, self.parallel, self.coverage)
        results = await executor.execute()

        self.report_generator.generate_html(results)
        self.report_generator.generate_json(results)

        self.all_results.append(results)
        return results

    async def run(self, suites: list[str]) -> None:
        """বাংলা মন্তব্য: এক বা একাধিক টেস্ট স্যুট রান করে"""
        try:
            await self.env_manager.setup()

            for suite_name in suites:
                await self.run_suite(suite_name)

            self.report_generator.generate_summary(self.all_results)

        finally:
            await self.env_manager.teardown()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """বাংলা মন্তব্য: CLI entry point"""
    parser = argparse.ArgumentParser(
        description="SupremeAI 2.0 — Integration Test Runner\nE2E টেস্ট অটোমেশন",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--env", "-e", default=DEFAULT_ENV,
                        choices=["test", "staging", "production"],
                        help="Test environment")
    parser.add_argument("--suite", "-s", default=DEFAULT_SUITE,
                        help=f"Test suite(s) — comma-separated. Available: {', '.join(TEST_SUITES.keys())}")
    parser.add_argument("--parallel", "-p", type=int, default=DEFAULT_PARALLEL,
                        help="Number of parallel workers")
    parser.add_argument("--coverage", "-c", action="store_true", default=COVERAGE_ENABLED,
                        help="Enable coverage reporting")
    parser.add_argument("--list-suites", "-l", action="store_true",
                        help="List available test suites")

    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

    if args.list_suites:
        print("\n📋 Available Test Suites:")
        print("-" * 50)
        for name, suite in TEST_SUITES.items():
            print(f"  {name:12} — {suite.description}")
            print(f"               Files: {', '.join(suite.test_files)}")
            print(f"               Requires: {', '.join(suite.requires)}")
        return

    suite_names = [s.strip() for s in args.suite.split(",")]

    async def run():
        runner = IntegrationTestRunner(
            env=args.env,
            parallel=args.parallel,
            coverage=args.coverage,
        )
        await runner.run(suite_names)

    asyncio.run(run())


if __name__ == "__main__":
    main()
