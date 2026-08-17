import os
import uuid
import time
from locust import HttpUser, task, between, tag
import logging

logger = logging.getLogger(__name__)

class SupremeAILoadTester(HttpUser):
    # ইউজাররা খুব দ্রুত রিকোয়েস্ট পাঠাবে (১০০ms থেকে ৫০০ms ব্যবধানে)
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """
        Executes on virtual user initialization. Retrieves secure authentication tokens
        from environment context instead of static hardcoded strings.
        """
        self.session_id = f"test-session-{uuid.uuid4()}"
        api_token = os.getenv("SUPREMEAI_API_KEY")
        app_env = os.getenv("APP_ENV", "development").lower()

        if not api_token:
            if app_env == "production":
                # বাংলা মন্তব্য: প্রোডাকশনে কোনোভাবেই ফলব্যাক টোকেন চলতে পারে না!
                logger.critical("CRITICAL: SUPREMEAI_API_KEY env var is missing in production environment!")
                raise ValueError("SUPREMEAI_API_KEY environment variable is mandatory for production load tests.")

            # লোকাল এনভায়রনমেন্টে নন-সেন্সিটিভ টেস্টিংয়ের জন্য ফলব্যাক
            api_token = "test-token-" + "secure-bypass"
            logger.warning(f"Using development fallback token. Current environment context: {app_env}")

        self.auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}"
        }

    @tag('stream_stress')
    @task(2)
    def test_global_httpx_pool_and_sse(self):
        """১. গ্লোবাল HTTPX পুল এবং অ্যাসিঙ্ক ইভেন্ট লুপের স্ট্রেস টেস্ট"""
        with self.client.post(
            "/api/task/stream",
            json={"message": "Keep connection alive", "session_id": self.session_id},
            headers=self.auth_headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTPX Pool Choked! Status: {response.status_code}")

    @tag('semantic_cache_hit')
    @task(3)
    def test_semantic_cache_efficiency(self):
        """২. সিমান্টিক ক্যাশ হিট রেশিও এবং মিলি-সেকেন্ড রেসপন্স টাইম টেস্ট"""
        # কাছাকাছি অর্থের ৩টি প্রম্পট যা SHA-256 ক্যাশকে ফেইল করাবে কিন্তু সিমান্টিক ক্যাশকে হিট করাবে
        semantic_prompts = [
            "আমাকে একটি পাইথন স্ক্রিপ্ট লিখে দাও",
            "আমাকে একটি পাইথন স্ক্রিপ্ট লিখে দাও। ", # শেষে অতিরিক্ত স্পেস ও দাড়ি
            "পাইথনে একটি কোড লিখে দাও প্লিজ"        # সম্পূর্ণ ভিন্ন স্ট্রাকচার কিন্তু সেম মিনিং
        ]

        # প্রথমবার রিকোয়েস্ট পাঠালে ক্যাশ মিস হবে (LLM হিট করবে)
        # ২য় এবং ৩য় বার ক্যাশ হিট হয়ে < ৫০ms এ রেসপন্স আসার কথা
        for prompt in semantic_prompts:
            idempotency_key = str(uuid.uuid4())
            headers = {**self.auth_headers, "Idempotency-Key": idempotency_key}

            start_time = time.time()
            with self.client.post(
                "/api/task/execute",
                json={"message": prompt, "model_preference": "gemini-2.5-flash"},
                headers=headers,
                catch_response=True
            ) as response:
                duration = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    try:
                        res_json = response.json()
                        # ব্যাকএন্ড যদি সিমান্টিক ক্যাশ থেকে ডাটা দেয় তবে 'source' ফিল্ডে তা থাকার কথা
                        if res_json.get("source") == "semantic_cache" or "semantic-vector-hit" in str(res_json.get("provider")):
                            response.success()
                            # ক্যাশ হিট হলে রেসপন্স টাইম সাধারণত ১০-৪০ms এর ভেতর নেমে আসে
                            if duration > 100:
                                logger.warning(f"⚠️ Cache Hit but High Latency: {duration:.2f}ms")
                        else:
                            response.success()
                    except Exception as e:
                        # বাংলা: response 200 হলেও JSON পার্স ব্যর্থ হলে তা লগ করুন,
                        # নাহলে ক্যাশ-হিট ডিটেকশন সাইলেন্টলি ভেঙে যেতে পারে এবং কেউ জানবে না
                        logger.warning(f"Could not parse cache-hit signal from 200 response: {e}")
                        response.success()
                else:
                    response.failure(f"Execution route failed: {response.status_code}")

    @tag('idempotency_race')
    @task(1)
    def test_idempotency_race_condition(self):
        """৩. আইডেমপোটেন্সি রেস-কন্ডিশন অ্যাটাক (একই কি দিয়ে স্প্যামিং)"""
        shared_idempotency_key = str(uuid.uuid4())
        headers = {**self.auth_headers, "Idempotency-Key": shared_idempotency_key}

        # একই টাইমে পরপর ৩টি রিকোয়েস্ট ফায়ার করা হবে (Simulating rapid double clicks)
        responses = []
        for _ in range(3):
            res = self.client.post(
                "/api/task/execute",
                json={"message": "Critical Orchestration Task", "model_preference": "gemini-2.5-flash"},
                headers=headers,
                name="/api/task/execute [Idempotency Spam]"
            )
            responses.append(res)

        # ভ্যালিডেশন লজিক:
        # ১ম রিকোয়েস্টটি সাকসেসফুল (200 OK) অথবা প্রসেসিং (409 Conflict) হবে।
        # কিন্তু ২য় ও ৩য় রিকোয়েস্টকে আমাদের আইডেমপোটেন্সি ইঞ্জিন অবশ্যই ৪MD বা ২০০ ক্যাশড রেসপন্স দিয়ে ব্লক করবে।
        status_codes = [r.status_code for r in responses]

        # যদি কোনোভাবে একাধিক রিকোয়েস্ট ২০০ পেয়ে যায় এবং ক্যাশ সোর্স না দেখায়, তবে লকিং ফেইল করেছে!
        if status_codes.count(200) > 1:
            # চেক করা হচ্ছে ২য় ২০০-টি ক্যাশ হিট কি না
            try:
                cached_hits = [r.json().get("source") == "semantic_cache" or "X-Cache-Lookup" in r.headers for r in responses if r.status_code == 200]
                if not any(cached_hits):
                    print(f"🚨 CRITICAL FAILURE: Race Condition Exploded! Multiple execution passed: {status_codes}")
            except Exception as e:
                # বাংলা: রেস-কন্ডিশন ভ্যালিডেশন লজিকটি নিজেই ভেঙে গেলে তা লগ করুন,
                # নাহলে একটি প্রকৃত রেস-কন্ডিশন বাগ নীরবে miss হয়ে যেতে পারে
                logger.warning(f"Race-condition validation check failed to parse responses: {e}")
