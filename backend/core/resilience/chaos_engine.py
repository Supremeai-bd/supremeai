import asyncio
import os
import random

from core.logging_config import logger

# বাংলা মন্তব্য (৩-স্তর টেস্টিং প্ল্যান Tier-2): ফল্ট-টাইপ তালিকা কনস্ট্যান্টে রাখা
# হলো যাতে টেস্ট সরাসরি রেফারেন্স করতে পারে। নতুন দুটি ফল্ট:
#   rate_limit_429 — LLM provider rate-limit storm সিমুলেশন (HTTP 429);
#   memory_pressure — OOM-adjacent চাপ সিমুলেশন (MemoryError)।
# দুটোই exception raise করে; caller (health_probes) নিজের try/except-এ
# status=down হিসেবে হ্যান্ডেল করে — এটাই প্রত্যাশিত degraded আচরণ।
CHAOS_FAULT_TYPES = [
    "latency",
    "timeout",
    "cache_evict",
    "llm_down",
    "rate_limit_429",
    "memory_pressure",
]


class ChaosEngine:
    def __init__(self):
        # Only enable if explicitly set to "True" to prevent accidental production chaos
        self.enabled = os.getenv("ENABLE_CHAOS_MODE", "False").lower() == "true"

    async def inject_fault(self, fault_type: str | None = None):
        """Randomly injects faults if chaos mode is enabled.

        বাংলা মন্তব্য (Tier-2): fault_type প্যারামিটার optional — দিলে সেই নির্দিষ্ট
        ফল্ট inject হবে (টেস্ট deterministic করার জন্য), না দিলে আগের মতো random।
        """
        if not self.enabled:
            return

        # 5% chance to inject a fault when called (fault_type explicitly দিলে skip)
        if fault_type is None and random.random() > 0.05:
            return

        chosen = fault_type or random.choice(CHAOS_FAULT_TYPES)
        if chosen == "latency":
            logger.warning("💉 Chaos: Injecting 2s latency to simulate network spike")
            await asyncio.sleep(2)
        elif chosen == "timeout":
            logger.critical("💉 Chaos: Injecting artificial TimeoutError")
            raise TimeoutError("Simulated Chaos Timeout")
        elif chosen == "cache_evict":
            logger.warning("💉 Chaos: Simulating Redis connection loss")
            # In a real scenario, this might close the redis connection
            # raise ConnectionError("Simulated Redis Connection Loss")
            pass
        elif chosen == "llm_down":
            logger.critical("💉 Chaos: Simulating LLM Provider failure")
            # We can raise a simulated exception or just rely on the timeout
            raise ConnectionError("Simulated LLM Provider Down")
        elif chosen == "rate_limit_429":
            # বাংলা মন্তব্য: provider rate-limit — gateway-এর _handle_rate_limit_error
            # পথ যাচাইয়ের জন্য; ConnectionError হিসেবে raise করা হয় কারণ inject_fault
            # HTTP response ফেরাতে পারে না (health-probe context)।
            logger.critical("💉 Chaos: Simulating provider rate-limit (HTTP 429 storm)")
            raise ConnectionError("Simulated Provider Rate Limit (HTTP 429)")
        elif chosen == "memory_pressure":
            # বাংলা মন্তব্য: OOM-adjacent চাপ — MemoryError raise; সত্যিকারের মেমরি
            # allocation করা হয় না (sandbox/CI-নিরাপদ)।
            logger.critical("💉 Chaos: Simulating memory pressure (OOM-adjacent)")
            raise MemoryError("Simulated Memory Pressure")
        else:
            # বাংলা মন্তব্য: অজানা fault_type — নীরবে উপেক্ষা না করে স্পষ্ট error
            raise ValueError(f"Unknown chaos fault type: {chosen!r}")


chaos_engine = ChaosEngine()
