#!/usr/bin/env python3
"""
packages/scripts/master_validator.py — স্বয়ংক্রিয় রেডিনেস অর্কেস্ট্রেটর।

সিস্টেম রিবুট বা প্রোডাকশন ডেপ্লয়মেন্টের ঠিক আগে এই স্ক্রিপ্টটি চলে। এটি পুরো
SupremeAI ইকোসিস্টেমের "Health & Config" স্ক্যান করে গ্রিন-সিগন্যাল দেয়।

প্রজেক্টের রিয়েল এনভায়রনমেন্ট কনভেনশন অনুযায়ী অ্যালাইন করা হয়েছে (backend/core/config.py):
  - SUPREMEAI_JWT_SECRET   (production-এ বাধ্যতামূলক, >=64 bytes)
  - SUPABASE_DATABASE_URL / SUPABASE_DATABASE_URL_POOLER  (DB)
  - OPENAI_API_KEY          (LLM Gateway)
  - REDIS_URL               (Distributed Cache / CostGuard — fail-open warning)

রান করুন:  python3 packages/scripts/master_validator.py
"""

import asyncio
import os
import sys

import httpx

# উইন্ডোজ কনসোল (cp1252) ইউনিকোড অক্ষর এনকোড করতে পারে না — তাই stdout/stderr
# জোর করে UTF-8 করা হচ্ছে, যেন রেডিনেস রিপোর্ট সব প্ল্যাটফর্মে ঠিকভাবে দেখা যায়।
if getattr(sys.stdout, "encoding", "").lower() not in ("utf-8", "utf8", ""):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001 - সর্বোচ্চ চেষ্টা; এটি কখনোই স্ক্যান আটকাবে না
        pass

# টার্মিনাল আউটপুট রঙিন করার জন্য ANSI কালার কোড
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# পরিচিত দুর্বল JWT সিক্রেট — এগুলো পাওয়া গেলে সাথে সাথে বুট আটকে দেওয়া হয়
WEAK_JWT_SECRETS = {"secret", "password", "123456", "changeme", "admin", "jwt_secret"}


class MasterValidator:
    """
    প্রোডাকশন রিবুটের আগে সিস্টেমের চূড়ান্ত প্রস্তুতি যাচাইকারী ক্লাস।
    এনভায়রনমেন্ট ভেরিয়েবল, এক্সটার্নাল API এবং জরুরি ইনফ্রাস্ট্রাকচার পরীক্ষা করে।

    errors তালিকায় কিছু থাকলে বুট বাতিল হয়; warnings কেবল সতর্ক করে,
    কিন্তু ডিপ্লয়মেন্ট আটকায় না।
    """

    def __init__(self):
        self.errors = []
        self.warnings = []

    def _env(self, key: str) -> str:
        """এনভায়রনমেন্ট ভেরিয়েবল পড়ে; অনুপস্থিত হলে ফাঁকা স্ট্রিং ফেরত দেয়।

        সামনে-পিছনে থাকা বাড়তি স্পেস ছেঁটে ফেলা হয়, কারণ কপি-পেস্টের সময়
        অসাবধানে যুক্ত হওয়া স্পেস ভুলভাবে "ভ্যালু আছে" বলে ধরা পড়তে পারে।
        """
        val = os.getenv(key)
        return val.strip() if isinstance(val, str) else ""

    async def check_environment_variables(self):
        """জরুরি সব এনভায়রনমেন্ট ভেরিয়েবল উপস্থিত ও বৈধ কি না যাচাই করে।"""
        print(f"{YELLOW}Checking Environment Integrity...{RESET}")

        # LLM গেটওয়ে — backend/core/config.py: openai_api_key (OPENAI_API_KEY)
        if not self._env("OPENAI_API_KEY"):
            self.errors.append("Missing critical environment variable: OPENAI_API_KEY")

        # JWT সিক্রেট — backend/core/config.py: SUPREMEAI_JWT_SECRET (fail-closed নীতি)
        jwt = self._env("SUPREMEAI_JWT_SECRET")
        if not jwt:
            self.errors.append("Missing critical environment variable: SUPREMEAI_JWT_SECRET")
        elif len(jwt) < 64:
            # ৬৪ বাইটের কম সিক্রেট ব্রুট-ফোর্স আক্রমণে দুর্বল, তাই সব পরিবেশেই প্রত্যাখ্যাত
            self.errors.append(
                f"SUPREMEAI_JWT_SECRET must be >= 64 bytes (current: {len(jwt)}). "
                "Config rejects weak secrets in all environments."
            )
        elif jwt.lower() in WEAK_JWT_SECRETS:
            self.errors.append("SUPREMEAI_JWT_SECRET is a known weak secret - change it immediately.")

        # ডাটাবেজ — সরাসরি সংযোগ অথবা পুলার, যেকোনো একটি থাকলেই চলবে
        if not (self._env("SUPABASE_DATABASE_URL") or self._env("SUPABASE_DATABASE_URL_POOLER")):
            self.errors.append(
                "Missing database URL: set SUPABASE_DATABASE_URL or SUPABASE_DATABASE_URL_POOLER"
            )

        # বুট করার সময় Redis ঐচ্ছিক, তবে multi_layer_cache ও swarm_pubsub-এর মতো
        # কিছু অংশ fail-closed — তাই এররের বদলে সতর্কবার্তা দেওয়া হচ্ছে
        if not self._env("REDIS_URL"):
            self.warnings.append(
                "REDIS_URL not set. CostGuard/cache run fail-closed - expect runtime errors "
                "until Redis is provisioned."
            )

        if self.errors:
            print(f"{RED}Environment has critical gaps{RESET}")
        else:
            print(f"{GREEN}Environment Configured{RESET}")

    async def check_llm_gateway(self):
        """OpenAI API কী বৈধ কি না তা models এন্ডপয়েন্টে পিং করে যাচাই করে।"""
        print(f"{YELLOW}Pinging LLM Gateway (OpenAI)...{RESET}")
        api_key = self._env("OPENAI_API_KEY")
        if not api_key:
            # কী অনুপস্থিত থাকার এররটি আগেই যোগ করা হয়েছে, তাই এখানে চুপচাপ ফিরে যাই
            return

        try:
            # ৫ সেকেন্ড টাইমআউট — রেডিনেস চেক যেন কখনো ঝুলে না থাকে
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if response.status_code == 200:
                    print(f"{GREEN}LLM Gateway Online{RESET}")
                else:
                    self.errors.append(
                        f"LLM Gateway rejected credentials (HTTP {response.status_code})"
                    )
        except httpx.RequestError as e:
            self.errors.append(f"LLM Gateway unreachable: {e}")

    async def check_redis_cache(self):
        """Redis সংযোগ জীবিত কি না তা ping কমান্ড দিয়ে পরীক্ষা করে।"""
        print(f"{YELLOW}Verifying Distributed Cache (Redis)...{RESET}")
        redis_url = self._env("REDIS_URL")
        if not redis_url:
            # URL না থাকলে আগেই সতর্কবার্তা দেওয়া হয়েছে — এখানে পরীক্ষা করার কিছু নেই
            return

        try:
            # redis লাইব্রেরি কেবল প্রয়োজনের সময় ইমপোর্ট করা হয়, যাতে Redis ছাড়া
            # পরিবেশেও স্ক্রিপ্টটি চালু হতে পারে
            import redis.asyncio as redis

            client = redis.from_url(redis_url)
            await client.ping()
            await client.aclose()
            print(f"{GREEN}Distributed Cache Online{RESET}")
        except Exception as e:  # noqa: BLE001 - রেডিনেস চেক কখনোই ক্র্যাশ করা যাবে না
            self.errors.append(f"Redis connection failed: {e}")

    async def run_all(self):
        """সব যাচাই ধাপ ক্রমান্বয়ে চালিয়ে চূড়ান্ত রিপোর্ট ছাপে।

        কোনো ক্রিটিক্যাল এরর থাকলে exit code 1 দিয়ে বের হয়, ফলে CI পাইপলাইন
        বা ডিপ্লয় স্ক্রিপ্ট স্বয়ংক্রিয়ভাবে থেমে যায়।
        """
        print("\n" + "=" * 50)
        print(" SUPREME-AI: MASTER SYSTEM VALIDATION")
        print("=" * 50 + "\n")

        await self.check_environment_variables()
        await self.check_llm_gateway()
        await self.check_redis_cache()

        print("\n" + "=" * 50)
        if self.errors:
            print(f"{RED}SYSTEM BOOT ABORTED! Critical Errors Found:{RESET}")
            for err in self.errors:
                print(f"  - {err}")
            sys.exit(1)
        else:
            if self.warnings:
                print(f"{YELLOW}Warnings:{RESET}")
                for warn in self.warnings:
                    print(f"  - {warn}")
            print(
                f"{GREEN}ALL SYSTEMS GO! The Autonomous Architecture is ready.{RESET}"
            )
            sys.exit(0)


if __name__ == "__main__":
    validator = MasterValidator()
    asyncio.run(validator.run_all())
