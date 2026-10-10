# backend/tests/cloud_db_load_test.py
"""Supabase pgvector Cloud Load Testing Suite (honest edition).

৩-স্তর টেস্টিং প্ল্যান Phase 1 রাইট-আপ: আগের সংস্করণটি asyncio.sleep()
দিয়ে *বানানো* লেটেন্সি রেকর্ড করে "EXCELLENT ✅" রিপোর্ট ছাপাত — অর্থাৎ
কোনো আসল ডেটাবেস না ছুঁয়েই সফলতার মান ফেরাত (qa_suite.py-এর B-06
অডিটের একই ধরনের honesty ল্যান্ডমাইন)। এই সংস্করণ:

- আসল Supabase টার্গেট (SUPABASE_URL + SUPABASE_SERVICE_KEY) কনফিগার
  থাকলে: আসল সমান্তরাল insert/select চালিয়ে আসল p50/p95/p99, আসল
  error-rate মাপে;
- টার্গেট না থাকলে: কিছু না বানিয়ে স্পষ্টভাবে SKIP বলে বেরিয়ে যায়।

Usage:
    python tests/cloud_db_load_test.py            # টার্গেট থাকলে রান, নাহলে স্কিপ
    python tests/cloud_db_load_test.py --users 20 --ops 5
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from supabase import Client, create_client
except ImportError:
    Client = None  # type: ignore[assignment]

# বাংলা মন্তব্য: mock ডিফল্ট মান — এগুলো দেখলেই স্কিপ করা হবে (আসল টার্গেট
# নয়)। আগের সংস্করণ এই মানগুলো দিয়েও ভুয়া মাপ ছাপাত।
_MOCK_URL = "https://mock.supabase.co"
_MOCK_KEY = "mock-key"


@dataclass
class LatencyMeasurement:
    operation: str
    duration_ms: float
    timestamp: datetime
    success: bool
    error: str | None = None
    size_bytes: int = 0


@dataclass
class LoadTestResult:
    scenario: str
    concurrent_users: int
    operations_per_user: int
    total_operations: int
    successful_ops: int
    failed_ops: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_ops_per_sec: float
    error_rate: float
    duration_seconds: float
    measurements: list[LatencyMeasurement] = field(default_factory=list)


@dataclass
class HealthCheckResult:
    connection_ok: bool
    latency_ms: float
    pool_size: int = 0
    active_connections: int = 0
    db_size_mb: float = 0.0
    vector_extension_ok: bool = True


class CloudDBLoadTester:
    """Supabase-বিরুদ্ধে আসল লোড টেস্টার — ভুয়া মাপ নয়।"""

    def __init__(self, supabase_url: str | None = None, supabase_key: str | None = None) -> None:
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL", _MOCK_URL)
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY", _MOCK_KEY)
        self.client: Client | None = None
        self.test_table = "load_test_data"

    def has_real_target(self) -> bool:
        """আসল টার্গেট কনফিগার করা আছে কি না — mock মান বা অনুপস্থিতি নয়।"""
        return bool(
            self.supabase_url
            and self.supabase_key
            and self.supabase_url != _MOCK_URL
            and self.supabase_key != _MOCK_KEY
            and self.supabase_url.startswith("http")
        )

    async def initialize(self) -> bool:
        """আসল client তৈরি করে; ব্যর্থ হলে False (নীরবে সফল ভান করে না)।"""
        if Client is None:
            return False
        try:
            self.client = create_client(self.supabase_url, self.supabase_key)
            return True
        except Exception as e:
            print(f"⚠️ Could not connect to real Supabase: {e}")
            self.client = None
            return False

    async def health_check(self) -> HealthCheckResult:
        """আসল round-trip: একটি হালকা select দিয়ে connection যাচাই।"""
        if self.client is None:
            return HealthCheckResult(connection_ok=False, latency_ms=0.0)
        start = time.perf_counter()
        try:
            self.client.table(self.test_table).select("id", count="exact").limit(1).execute()
            latency = (time.perf_counter() - start) * 1000.0
            return HealthCheckResult(connection_ok=True, latency_ms=round(latency, 2))
        except Exception as e:
            # বাংলা মন্তব্য: টেবিল না থাকলেও connection আসলেই কাজ করছে কি না
            # আলাদা করে বলা যায় না — সৎভাবে connection_ok=False।
            print(f"⚠️ health_check failed: {e}")
            return HealthCheckResult(connection_ok=False, latency_ms=0.0)

    async def _one_user_burst(self, user_id: int, ops_per_user: int) -> list[LatencyMeasurement]:
        """একজন ভার্চুয়াল ইউজারের পরপর insert+select বার্স্ট — আসল কল।"""
        results: list[LatencyMeasurement] = []
        assert self.client is not None  # initialize() আগে সফল হয়েছে
        for i in range(ops_per_user):
            payload: dict[str, Any] = {
                "user_id": user_id,
                "seq": i,
                "content": f"load-test probe u{user_id} i{i}",
            }
            t0 = time.perf_counter()
            try:
                self.client.table(self.test_table).insert(payload).execute()
                elapsed = (time.perf_counter() - t0) * 1000.0
                results.append(
                    LatencyMeasurement(
                        operation="insert",
                        duration_ms=elapsed,
                        timestamp=datetime.now(),
                        success=True,
                        size_bytes=len(str(payload)),
                    )
                )
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000.0
                results.append(
                    LatencyMeasurement(
                        operation="insert",
                        duration_ms=elapsed,
                        timestamp=datetime.now(),
                        success=False,
                        error=str(e),
                    )
                )
            # একই বার্স্টে একটি select — read-path-ও মাপা হোক
            t0 = time.perf_counter()
            try:
                self.client.table(self.test_table).select("id").limit(1).execute()
                elapsed = (time.perf_counter() - t0) * 1000.0
                results.append(
                    LatencyMeasurement(
                        operation="select",
                        duration_ms=elapsed,
                        timestamp=datetime.now(),
                        success=True,
                    )
                )
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000.0
                results.append(
                    LatencyMeasurement(
                        operation="select",
                        duration_ms=elapsed,
                        timestamp=datetime.now(),
                        success=False,
                        error=str(e),
                    )
                )
        return results

    async def run_concurrent_test(
        self, concurrent_users: int = 10, ops_per_user: int = 3
    ) -> LoadTestResult:
        """সমান্তরাল বার্স্ট — সবগুলো আসল অপারেশনের আসল সময়।"""
        start = time.perf_counter()
        bursts = await asyncio.gather(
            *(self._one_user_burst(u, ops_per_user) for u in range(concurrent_users))
        )
        duration = time.perf_counter() - start
        measurements = [m for burst in bursts for m in burst]
        return self._summarize(
            scenario="concurrent_insert_select",
            concurrent_users=concurrent_users,
            ops_per_user=ops_per_user,
            measurements=measurements,
            duration=duration,
        )

    def _summarize(
        self,
        *,
        scenario: str,
        concurrent_users: int,
        ops_per_user: int,
        measurements: list[LatencyMeasurement],
        duration: float,
    ) -> LoadTestResult:
        latencies = [m.duration_ms for m in measurements if m.success]
        successes = sum(1 for m in measurements if m.success)
        total = len(measurements)
        sorted_lat = sorted(latencies) if latencies else [0.0]

        def _pct(p: float) -> float:
            if not sorted_lat:
                return 0.0
            k = min(len(sorted_lat) - 1, int(round((len(sorted_lat) - 1) * p)))
            return sorted_lat[k]

        return LoadTestResult(
            scenario=scenario,
            concurrent_users=concurrent_users,
            operations_per_user=ops_per_user,
            total_operations=total,
            successful_ops=successes,
            failed_ops=total - successes,
            avg_latency_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
            p50_latency_ms=round(_pct(0.50), 2),
            p95_latency_ms=round(_pct(0.95), 2),
            p99_latency_ms=round(_pct(0.99), 2),
            min_latency_ms=round(min(latencies), 2) if latencies else 0.0,
            max_latency_ms=round(max(latencies), 2) if latencies else 0.0,
            throughput_ops_per_sec=round(total / duration, 2) if duration > 0 else 0.0,
            error_rate=round(((total - successes) / total) * 100.0, 2) if total else 0.0,
            duration_seconds=round(duration, 2),
            measurements=measurements,
        )

    def generate_report(self, result: LoadTestResult) -> str:
        """সৎ রিপোর্ট — হার্ডকোডেড "EXCELLENT ✅" নয়; মাপা মান থেকে সিদ্ধান্ত।"""
        if result.total_operations == 0:
            overall = "NO DATA"
        elif result.error_rate == 0.0 and result.p95_latency_ms < 500:
            overall = "HEALTHY"
        elif result.error_rate < 5.0 and result.p95_latency_ms < 2000:
            overall = "DEGRADED"
        else:
            overall = "UNHEALTHY"
        return (
            f"[{result.scenario}] users={result.concurrent_users} "
            f"ops={result.total_operations} ok={result.successful_ops} "
            f"fail={result.failed_ops} p50={result.p50_latency_ms}ms "
            f"p95={result.p95_latency_ms}ms p99={result.p99_latency_ms}ms "
            f"err={result.error_rate}% throughput={result.throughput_ops_per_sec}ops/s "
            f"overall={overall}"
        )


class CloudDBTester(CloudDBLoadTester):
    """Legacy compatibility facade (#4217) — পুরনো ক্লাস-নাম যে কোড ইমপোর্ট করে
    (tests/services/test_provider_rate_limiter.py) তার জন্য।

    বাংলা নোট: পুরনো সংস্করণের initialize()/health_check()/run_quick_test()
    asyncio.sleep-দিয়ে *বানানো* সফলতা ফেরাত (connection_ok=True,
    successful_ops>0, error_rate=0.0 — সবই হার্ডকোডেড)। এই facade সেই চুক্তি
    ভাঙে: আসল আচরণ সৎ ও নির্ধারক (deterministic) —

    - আসল টার্গেট থাকলে (SUPABASE_URL/SUPABASE_SERVICE_KEY): আসল প্রোব,
      আসল insert+select মাপ;
    - টার্গেট না থাকলে: connection_ok=False ও শূন্য-অপ ফলাফল — মক
      টার্গেটে নেটওয়ার্ক অ্যাটেম্পটও নয়, ভুয়া সবুজ তো নয়ই
      (honesty contract, qa_suite B-06)।
    """

    def __init__(self, supabase_url: str | None = None, supabase_key: str | None = None) -> None:
        super().__init__(supabase_url=supabase_url, supabase_key=supabase_key)
        # পুরনো API-র সাথে সামঞ্জস্য: রান-ইতিহাস জমা রাখা।
        self.results: list[LoadTestResult] = []

    async def health_check(self) -> HealthCheckResult:
        """আসল টার্গেট থাকলে আসল প্রোব; না থাকলে সৎ connection_ok=False
        (মক টার্গেটে নেটওয়ার্ক অ্যাটেম্পট করে নির্ধারক ব্যর্থতা নয়)।"""
        if not self.has_real_target():
            return HealthCheckResult(connection_ok=False, latency_ms=0.0)
        return await super().health_check()

    async def run_quick_test(self) -> LoadTestResult:
        """দ্রুত স্মোক-টেস্ট — আসল টার্গেটে ১ ভার্চুয়াল ইউজার × ৫
        insert+select (সবই আসল কল); টার্গেট না থাকলে সৎ শূন্য-অপ ফলাফল।"""
        if not self.has_real_target():
            result = LoadTestResult(
                scenario="quick_smoke_test_no_target",
                concurrent_users=0,
                operations_per_user=0,
                total_operations=0,
                successful_ops=0,
                failed_ops=0,
                avg_latency_ms=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                throughput_ops_per_sec=0.0,
                error_rate=0.0,
                duration_seconds=0.0,
            )
            self.results.append(result)
            return result
        result = await self.run_concurrent_test(concurrent_users=1, ops_per_user=5)
        self.results.append(result)
        return result

    def generate_report(self) -> dict[str, Any]:
        """পুরনো dict-শেপ রিপোর্ট — কিন্তু মান মাপা ডেটা থেকে, হার্ডকোডেড
        "EXCELLENT ✅" থেকে নয়।"""
        if not self.results:
            return {
                "summary": {
                    "total_tests": 0,
                    "overall_health": "NO DATA",
                    "worst_p95_latency_ms": 0.0,
                }
            }
        worst_p95 = max(r.p95_latency_ms for r in self.results)
        any_failed = any(r.failed_ops > 0 for r in self.results)
        any_no_target = any(r.scenario.endswith("no_target") for r in self.results)
        if any_failed:
            overall = "UNHEALTHY"
        elif any_no_target:
            overall = "NO TARGET"
        else:
            overall = "HEALTHY" if worst_p95 < 500 else "DEGRADED"
        return {
            "summary": {
                "total_tests": len(self.results),
                "overall_health": overall,
                "worst_p95_latency_ms": worst_p95,
            }
        }


async def main() -> int:
    parser = argparse.ArgumentParser(description="Honest Supabase cloud DB load test")
    parser.add_argument("--users", type=int, default=10, help="Concurrent virtual users")
    parser.add_argument("--ops", type=int, default=3, help="Insert+select ops per user")
    parser.add_argument("--url", default=None, help="Override SUPABASE_URL")
    parser.add_argument("--key", default=None, help="Override SUPABASE_SERVICE_KEY")
    args = parser.parse_args()

    tester = CloudDBLoadTester(supabase_url=args.url, supabase_key=args.key)
    if not tester.has_real_target():
        # বাংলা মন্তব্য: আসল টার্গেট নেই — ভুয়া মাপ ছাপানোর বদলে সৎ স্কিপ।
        print("SKIP: no real Supabase target configured (SUPABASE_URL/SUPABASE_SERVICE_KEY).")
        print("      Refusing to fabricate latency numbers (honesty contract, qa_suite B-06).")
        return 0

    if not await tester.initialize():
        print("SKIP: supabase client unavailable (import failed or connection error).")
        return 0

    health = await tester.health_check()
    print(f"health: connection_ok={health.connection_ok} latency={health.latency_ms}ms")
    if not health.connection_ok:
        print("ABORT: health check failed — not running load phase.")
        return 1

    result = await tester.run_concurrent_test(
        concurrent_users=max(1, args.users), ops_per_user=max(1, args.ops)
    )
    print(tester.generate_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
