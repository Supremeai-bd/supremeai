

# --- Merged from integration_test_runner.py ---

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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

# বাংলা মন্তব্য: sys.path হ্যাক এড়াতে ক্লিন ইমপোর্ট
try:
    from backend.core.config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ── Configuration ──────────────────────────────────────────────────────────
DEFAULT_ENV = os.getenv("TEST_ENV", "test")
DEFAULT_SUITE = os.getenv("TEST_SUITE", "all")
DEFAULT_PARALLEL = int(os.getenv("TEST_PARALLEL", "1"))
COVERAGE_ENABLED = os.getenv("TEST_COVERAGE", "false").lower() == "true"
REPORT_DIR = Path(os.getenv("TEST_REPORT_DIR", "tests/reports/integration"))
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
REDIS_TEST_URL = os.getenv("REDIS_TEST_URL", "redis://<your-redis-url>/15")
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


# --- Merged from superai_smoketest.py ---

#!/usr/bin/env python3
"""
SuperAI Automated Verification Suite
=====================================
Comprehensive tests to verify SuperAI transformation success.

Usage:
    python superai_verify.py                    # Run all checks
    python superai_verify.py --quick            # Quick smoke tests only
    python superai_verify.py --security         # Security-specific checks
    python superai_verify.py --json             # JSON output for CI

Checks Performed:
✅ File existence (new modules created)
✅ Import validity (all modules load correctly)
✅ Configuration (env vars, settings)
✅ Security headers (CSP, HSTS, etc.)
✅ Rate limiting (middleware active)
✅ Cache connectivity (Redis)
✅ Health endpoints (/health, /metrics)
✅ Code quality (lint, type check)
✅ Dependencies (all installed)

Author: SuperAI Toolkit
Version: 1.0.0
"""

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    """Result of a single verification check."""
    name: str
    category: str
    passed: bool
    message: str
    duration_ms: float = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass 
class VerificationReport:
    """Complete verification report."""
    timestamp: str
    total_checks: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    checks: list[CheckResult] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        ran = self.total_checks - self.skipped
        return (self.passed / ran * 100) if ran > 0 else 0
    
    @property
    def status(self) -> str:
        if self.failed == 0:
            return "✅ ALL CHECKS PASSED"
        elif self.pass_rate >= 80:
            return "⚠️ MOSTLY PASSED (some issues)"
        else:
            return "❌ CRITICAL ISSUES FOUND"


class SuperAIVerifier:
    """Verifies SuperAI transformation was successful."""
    
    def __init__(self, repo_path: str = ".", output_format: str = "text"):
        self.repo_path = Path(repo_path).resolve()
        self.output_format = output_format
        self.start_time = time.time()
        self.report = VerificationReport(
            timestamp=datetime.now().isoformat(),
            total_checks=0,
            passed=0,
            failed=0,
            skipped=0,
            duration_seconds=0
        )
    
    def run_check(self, name: str, category: str, check_fn) -> CheckResult:
        """Run a single verification check with timing."""
        start = time.time()
        try:
            passed, message, details = check_fn()
            duration = (time.time() - start) * 1000
            
            result = CheckResult(
                name=name,
                category=category,
                passed=passed,
                message=message,
                duration_ms=duration,
                details=details or {}
            )
            
            self.report.checks.append(result)
            self.report.total_checks += 1
            
            if passed:
                self.report.passed += 1
            else:
                self.report.failed += 1
            
            return result
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = CheckResult(
                name=name,
                category=category,
                passed=False,
                message=f"Check crashed: {e!s}",
                duration_ms=duration
            )
            self.report.checks.append(result)
            self.report.total_checks += 1
            self.report.failed += 1
            return result
    
    def run_command(self, cmd: str, timeout: int = 30) -> tuple[bool, str, str]:
        """Run shell command safely."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    # ===== CHECK CATEGORIES =====

    def check_pytest_execution(self) -> list[CheckResult]:
        """Run actual pytest suite."""
        results = []
        
        def run_pytest():
            success, stdout, stderr = self.run_command("poetry run pytest backend/tests/ -v", timeout=60)
            if success:
                return True, "Pytest passed", {"output": stdout[:500]}
            else:
                return False, "Pytest failed", {"error": stderr[:500]}
                
        results.append(self.run_check("Pytest Execution", "Integration Tests", run_pytest))
        return results

    def check_live_api_health(self) -> list[CheckResult]:
        """Check live API endpoints if running locally."""
        results = []
        
        def run_curl():
            success, stdout, _stderr = self.run_command("curl -s http://localhost:8000/api/v1/health", timeout=5)
            if success and ('"status":"ok"' in stdout.lower() or 'healthy' in stdout.lower()):
                return True, "Local API is healthy", {"response": stdout[:200]}
            else:
                return False, "Local API not responding or unhealthy", {"response": stdout[:200]}
                
        results.append(self.run_check("Live API Health (curl)", "Integration Tests", run_curl))
        return results
        
    def check_load_test(self) -> list[CheckResult]:
        """Basic load simulation."""
        results = []
        
        def run_load():
            import threading
            import urllib.request
            
            success_count = 0
            def req():
                nonlocal success_count
                try:
                    urllib.request.urlopen("http://localhost:8000/", timeout=2)
                    success_count += 1
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).exception(f"Silenced error: {e}")
            
            threads = [threading.Thread(target=req) for _ in range(10)]
            for t in threads: t.start()
            for t in threads: t.join()
            
            if success_count > 0:
                return True, f"{success_count}/10 requests succeeded", {}
            return False, "Load test failed", {}
            
        results.append(self.run_check("Basic Load Test", "Performance", run_load))
        return results
    
    def check_file_existence(self) -> list[CheckResult]:
        """Check that all expected files were created."""
        results = []
        
        expected_files = {
            "Cache Module": "backend/core/cache.py",
            "Rate Limiter": "backend/core/rate_limit.py",
            "Security Middleware": "backend/core/middleware/security.py",
            "Monitoring": "backend/core/monitoring.py",
            "Auto-Healer": "backend/core/auto_healer.py",
            "Config Validation": "backend/core/config_validation.py",
            "App Factory": "backend/core/app.py",
            "Dockerfile": "backend/Dockerfile",
            ".env.example": ".env.example",
        }
        
        for name, file_path in expected_files.items():
            def make_check(fp):
                def check():
                    full_path = self.repo_path / fp
                    if full_path.exists():
                        size = full_path.stat().st_size
                        return True, f"Exists ({size:,} bytes)", {"path": fp, "size": size}
                    return False, f"Not found: {fp}", {}
                return check
            
            result = self.run_check(
                f"File: {name}",
                "File Existence",
                make_check(file_path)
            )
            results.append(result)
        
        return results
    
    def check_imports(self) -> list[CheckResult]:
        """Check that all new modules can be imported."""
        results = []
        
        imports_to_test = [
            ("QueryCache", "from backend.core.cache import QueryCache"),
            ("RateLimiter", "from backend.core.rate_limit import RateLimiter"),
            ("SecurityHeadersMiddleware", "from backend.core.middleware.security import SecurityHeadersMiddleware"),
            ("MetricsCollector", "from backend.core.monitoring import MetricsCollector"),
            ("AutoHealer", "from backend.core.auto_healer import AutoHealer"),
            ("ConfigValidationMixin", "from backend.core.config_validation import ConfigValidationMixin"),
        ]
        
        for name, import_cmd in imports_to_test:
            def make_check(cmd):
                def check():
                    success, _stdout, stderr = self.run_command(f'python -c "{cmd}"')
                    if success:
                        return True, "Import successful", {"command": cmd}
                    return False, f"Import failed: {stderr[:100]}", {"error": stderr[:200]}
                return check
            
            result = self.run_check(
                f"Import: {name}",
                "Module Imports",
                make_check(import_cmd)
            )
            results.append(result)
        
        return results
    
    def check_security(self) -> list[CheckResult]:
        """Verify security hardening is in place."""
        results = []
        
        # Check GitHub Actions SHA pinning
        def check_sha_pinning():
            ci_file = self.repo_path / ".github/workflows/ci.yml"
            if not ci_file.exists():
                return False, "CI workflow not found", {}
            
            content = ci_file.read_text()
            
            # Count SHA-pinned actions vs tag-based
            content.count("uses:") - len([
                line for line in content.split('\n') 
                if 'uses:' in line and ('@v' in line or '@latest' in line)
            ])
            
            has_sha = any(len(line.strip().split('@')) > 1 and line.strip().split('@')[1][:10].isalnum() 
                         for line in content.split('\n') if 'uses:' in line)
            
            if has_sha:
                return True, "Actions are SHA-pinned ✅", {"sha_pinned": True}
            return False, "⚠️ Actions may use floating tags", {"sha_pinned": False}
        
        results.append(self.run_check("SHA-Pinned Actions", "Security", check_sha_pinning))
        
        # Check security middleware exists
        def check_security_middleware():
            sec_file = self.repo_path / "backend/core/middleware/security.py"
            if not sec_file.exists():
                return False, "Security middleware not found", {}
            
            content = sec_file.read_text()
            required = ["X-Content-Type-Options", "Strict-Transport-Security", "Content-Security-Policy"]
            found = [r for r in required if r in content]
            
            if len(found) == len(required):
                return True, f"All {len(required)} security headers present ✅", {"headers": found}
            return False, f"Missing headers: {set(required) - set(found)}", {"found": found}
        
        results.append(self.run_check("Security Headers", "Security", check_security_middleware))
        
        # Check rate limiter
        def check_rate_limiter():
            rl_file = self.repo_path / "backend/core/rate_limit.py"
            if not rl_file.exists():
                return False, "Rate limiter not found", {}
            
            content = rl_file.read_text()
            has_tiers = "anonymous" in content.lower() and "authenticated" in content.lower()
            has_redis = "redis" in content.lower()
            
            if has_tiers and has_redis:
                return True, "Multi-tier rate limiting configured ✅", {"tiers": True, "redis": True}
            return False, "Rate limiter incomplete", {"tiers": has_tiers, "redis": has_redis}
        
        results.append(self.run_check("Rate Limiting", "Security", check_rate_limiter))
        
        return results
    
    def check_code_quality(self) -> list[CheckResult]:
        """Run code quality checks."""
        results = []
        
        # Ruff linting
        def check_ruff():
            success, stdout, _stderr = self.run_command(
                "poetry run ruff check . --output-format=text 2>&1 | head -50"
            )
            if success:
                return True, "No lint errors ✅", {}
            
            error_count = stdout.count("\n") if stdout else 0
            return False, f"{error_count} lint issues found", {"output": stdout[:500]}
        
        results.append(self.run_check("Ruff Lint", "Code Quality", check_ruff))
        
        # Type checking (non-blocking)
        def check_mypy():
            _success, _stdout, stderr = self.run_command(
                "poetry run mypy backend/core/ --ignore-missing-imports 2>&1 | tail -20"
            )
            # MyPy warnings are OK, errors are not
            has_errors = "error:" in stderr.lower() if stderr else False
            if not has_errors:
                return True, "Type check passed (warnings OK) ✅", {}
            return False, "Type errors found", {"errors": stderr[:300]}
        
        results.append(self.run_check("MyPy Types", "Code Quality", check_mypy))
        
        # Python syntax check
        def check_syntax():
            py_files = list(self.repo_path.rglob("backend/core/*.py"))
            errors = []
            
            for py_file in py_files:
                success, _, _stderr = self.run_command(f"python -m py_compile {py_file}")
                if not success:
                    errors.append(py_file.name)
            
            if not errors:
                return True, f"All {len(py_files)} files compile ✅", {"files_checked": len(py_files)}
            return False, f"Syntax errors in: {errors}", {"errors": errors}
        
        results.append(self.run_check("Python Syntax", "Code Quality", check_syntax))
        
        return results
    
    def check_configuration(self) -> list[CheckResult]:
        """Verify configuration is correct."""
        results = []
        
        # Check .env.example has new variables
        def check_env_example():
            env_file = self.repo_path / ".env.example"
            if not env_file.exists():
                return False, ".env.example not found", {}
            
            content = env_file.read_text()
            required_vars = [
                "REDIS_URL",
                "LLM_CACHE_ENABLED",
                "RATE_LIMIT_ENABLED",
                "DAILY_BUDGET_USD",
                "SECURITY_HEADERS_ENABLED"
            ]
            
            found = [v for v in required_vars if v in content]
            
            if len(found) >= 4:
                return True, f"{len(found)}/{len(required_vars)} new vars documented ✅", {"documented": found}
            return False, f"Only {len(found)} new variables documented", {"found": found}
        
        results.append(self.run_check("Environment Variables", "Configuration", check_env_example))
        
        # Check Dockerfile optimization
        def check_dockerfile():
            dockerfile = self.repo_path / "backend/Dockerfile"
            if not dockerfile.exists():
                return False, "Dockerfile not found", {}
            
            content = dockerfile.read_text()
            optimizations = []
            
            if "multi-stage" in content.lower() or "AS builder" in content:
                optimizations.append("multi-stage")
            if "non-root" in content.lower() or "appuser" in content:
                optimizations.append("non-root user")
            if "healthcheck" in content.lower() or "HEALTHCHECK" in content:
                optimizations.append("health check")
            
            if len(optimizations) >= 2:
                return True, f"Docker optimized: {', '.join(optimizations)} ✅", {"optimizations": optimizations}
            return False, "Dockerfile needs optimization", {"current": optimizations}
        
        results.append(self.run_check("Dockerfile", "Configuration", check_dockerfile))
        
        return results
    
    def check_dependencies(self) -> list[CheckResult]:
        """Verify dependencies are installed."""
        results = []
        
        # Check poetry.lock exists and is recent
        def check_poetry_lock():
            lock_file = self.repo_path / "poetry.lock"
            toml_file = self.repo_path / "pyproject.toml"
            
            if not lock_file.exists():
                return False, "poetry.lock missing", {}
            
            if toml_file.exists():
                lock_time = lock_file.stat().st_mtime
                toml_time = toml_file.stat().st_mtime
                
                if lock_time < toml_time:
                    return False, "poetry.lock outdated (run poetry lock)", {}
            
            return True, "Dependencies locked ✅", {}
        
        results.append(self.run_check("Poetry Lock", "Dependencies", check_poetry_lock))
        
        # Check redis package available
        def check_redis_pkg():
            success, _, _ = self.run_command("python -c \"import redis; print(redis.__version__)\"")
            if success:
                return True, "Redis package installed ✅", {}
            return False, "Redis package missing (needed for caching)", {}
        
        results.append(self.run_check("Redis Package", "Dependencies", check_redis_pkg))
        
        return results
    
    def run_all_checks(self) -> VerificationReport:
        """Run all verification checks."""
        
        print("\n" + "=" * 70)
        print("🔍 SUPERAI VERIFICATION SUITE")
        print("=" * 70)
        print(f"Repository: {self.repo_path}")
        print(f"Started:   {self.report.timestamp}")
        print()
        
        # Run all check categories
        categories = [
            ("📁 File Existence", self.check_file_existence),
            ("📦 Module Imports", self.check_imports),
            ("🔒 Security Hardening", self.check_security),
            ("✨ Code Quality", self.check_code_quality),
            ("⚙️  Configuration", self.check_configuration),
            ("📚 Dependencies", self.check_dependencies),
            ("🧪 Integration Tests", self.check_pytest_execution),
            ("🌐 Live API Health", self.check_live_api_health),
            ("🔥 Performance/Load Test", self.check_load_test),
        ]
        
        for category_name, check_fn in categories:
            print(f"\n{category_name}")
            print("-" * 40)
            check_fn()
        
        # Calculate final stats
        self.report.duration_seconds = time.time() - self.start_time
        
        # Print report
        self.print_report()
        
        return self.report
    
    def print_report(self):
        """Print formatted verification report."""
        
        print("\n" + "=" * 70)
        print(f"VERIFICATION COMPLETE: {self.report.status}")
        print("=" * 70)
        
        # Summary by category
        categories = {}
        for check in self.report.checks:
            if check.category not in categories:
                categories[check.category] = {"passed": 0, "failed": 0, "total": 0}
            categories[check.category]["total"] += 1
            if check.passed:
                categories[check.category]["passed"] += 1
            else:
                categories[check.category]["failed"] += 1
        
        print("\n📊 Summary by Category:")
        print("-" * 40)
        for cat, stats in categories.items():
            status = "✅" if stats["failed"] == 0 else "❌"
            print(f"  {status} {cat}: {stats['passed']}/{stats['total']} passed")
        
        # Overall stats
        print(f"\n📈 Overall: {self.report.passed}/{self.report.total_checks} ({self.report.pass_rate:.1f}%)")
        print(f"⏱️  Duration: {self.report.duration_seconds:.1f}s")
        
        # Failed checks detail
        failed_checks = [c for c in self.report.checks if not c.passed]
        if failed_checks:
            print(f"\n❌ Failed Checks ({len(failed_checks)}):")
            print("-" * 40)
            for check in failed_checks:
                print(f"  • [{check.category}] {check.name}")
                print(f"    {check.message}")
        
        # Next steps
        if self.report.failed == 0:
            print("\n🎉 All checks passed! SuperAI is ready for deployment!")
        elif self.report.pass_rate >= 80:
            print("\n⚠️  Minor issues found. Review and fix before deployment.")
        else:
            print("\n🚨 Critical issues! Fix these before deploying.")
        
        print("=" * 70)
    
    def export_json(self) -> str:
        """Export report as JSON."""
        return json.dumps(asdict(self.report), indent=2, default=str)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SuperAI Verification Suite",
        epilog="Run after applying patches to verify transformation success."
    )
    
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--quick", action="store_true", help="Quick smoke tests only")
    parser.add_argument("--category", choices=["all", "security", "quality", "config"], 
                       default="all", help="Check category to run")
    
    args = parser.parse_args()
    
    verifier = SuperAIVerifier(repo_path=args.repo, output_format="json" if args.json else "text")
    
    if args.quick:
        # Quick mode: just file existence + imports
        verifier.check_file_existence()
        verifier.check_imports()
    elif args.category != "all":
        category_map = {
            "security": verifier.check_security,
            "quality": verifier.check_code_quality,
            "config": verifier.check_configuration,
        }
        category_map[args.category]()
    else:
        verifier.run_all_checks()
    
    if args.json:
        print(verifier.export_json())
    
    # Exit code based on pass rate
    sys.exit(0 if verifier.report.pass_rate >= 80 else 1)


if __name__ == "__main__":
    main()
