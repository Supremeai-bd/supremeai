"""SupremeAI Locust load profiles — ৩-স্তর টেস্টিং প্ল্যান Tier-1 (Phase 1)।

আগের সংস্করণের ৩টি টার্গেট URL-ই মৃত ছিল (openapi.json-এ নেই):
GET /api/skills, POST /api/task, GET /api/task/stream/{id}।
এই সংস্করণ openapi.json-এ যাচাইকৃত রুট + পেলোড স্কিমা ব্যবহার করে এবং
পরিকল্পনা অনুযায়ী ৩টি ইউজার পার্সোনা সিমুলেট করে (ওজন ৬:৩:১ = ৬০/৩০/১০):

- LightUser (weight 6): সাধারণ চ্যাট/কমপ্লিশন + হেলথ প্রোব — সবচেয়ে হালকা।
- HeavyKnowledgeUser (weight 3): ফাইল আপলোড + ইউনিফায়েড মেমোরি store/query
  + RAG হাইব্রিড সার্চ — ভেক্টর/মেমোরি পাথের ভারী চাপ।
- TaskAgentUser (weight 1): টাস্ক/এজেন্ট এক্সিকিউশন ট্রিগার + SSE হোল্ড।

Auth: LOAD_TEST_TOKEN env var (Bearer)। /health পাবলিক পাথ — auth ছাড়া।
Nightly load job (nightly-ops.yml) এই ফাইলটি ব্যবহার করে।
"""

import os
import random
import time
import uuid

from locust import HttpUser, between, events, task

# ব্রাউজার-অটোমেশন সেশন স্পন করা লোড টেস্টে সার্ভারে আসল chromium প্রসেস
# তৈরি করে — ডিফল্টে বন্ধ; সচেতন অপ্ট-ইনে চালু।
_INCLUDE_BROWSER_SESSIONS = os.getenv("LOAD_TEST_INCLUDE_BROWSER", "false").lower() == "true"

# একটি বৈধ 1x1 PNG (লোড টেস্ট আপলোড প্রোবের জন্য) — base64-হার্ডকোড, নেটওয়ার্ক নয়
import base64

_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNg"
    "YGBgAAAABQABh6FO1AAAAABJRU5ErkJggg=="
)
_PNG_1X1_BYTES = base64.b64decode(_PNG_1X1_B64)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


class _BaseSupremeAIUser(HttpUser):
    """Common auth bootstrap — subclass গুলো এটি ব্যবহার করে।"""

    abstract = True
    wait_time = between(1.0, 3.0)

    def on_start(self):
        self.auth_token = os.environ.get("LOAD_TEST_TOKEN", "")
        self.headers = {"Content-Type": "application/json", **_auth_headers(self.auth_token)}


class LightUser(_BaseSupremeAIUser):
    """পার্সোনা ১ (৬০%): সাধারণ চ্যাট/কমপ্লিশন ইউজার।

    POST /api/chat/completion — CompletionRequest স্কিমা (prefix/suffix/filePath/language,
    সব required)। ছোট প্রম্পট যাতে রেসপন্স দ্রুত আসে।
    """

    weight = 6

    @task(3)
    def chat_completion(self):
        payload = {
            "prefix": "def add(a, b):\n    # ",
            "suffix": "\n    return a + b\n",
            "filePath": "loadtest_light.py",
            "language": "python",
        }
        with self.client.post(
            "/api/chat/completion",
            json=payload,
            headers=self.headers,
            timeout=(5, 30),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"chat/completion failed: {response.status_code} - {response.text[:200]}"
                )

    @task(1)
    def health_probe(self):
        # /health পাবলিক পাথ — auth হেডার লাগে না
        with self.client.get("/health", timeout=(5, 10), catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"health failed: {response.status_code}")


class HeavyKnowledgeUser(_BaseSupremeAIUser):
    """পার্সোনা ২ (৩০%): ভেক্টর সার্চ + মেমোরি রিট্রিভাল + ফাইল আপলোড।

    এই পার্সোনা unified memory + RAG + upload পাথে ভারী চাপ তৈরি করে —
    Tier-1 পরিকল্পনার "Heavy Knowledge User"।
    """

    weight = 3

    @task(2)
    def memory_store_and_query(self):
        session_id = f"loadtest-{uuid.uuid4().hex[:10]}"
        # POST /unified-memory/long-term/store — query-param API (openapi অনুযায়ী)
        params = {
            "session_id": session_id,
            "agent_type": "load_test",
            "task_type": "knowledge_ingest",
            "content": f"Load-test knowledge probe {random.randint(0, 9999)}: "
            "SupremeAI vector memory concurrent write path validation.",
        }
        with self.client.post(
            "/unified-memory/long-term/store",
            params=params,
            headers=self.headers,
            timeout=(5, 30),
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            else:
                response.failure(
                    f"memory store failed: {response.status_code} - {response.text[:200]}"
                )

        # GET /unified-memory/long-term/query — query param + top_k (max 20)
        with self.client.get(
            "/unified-memory/long-term/query",
            params={"query": "load test knowledge probe", "top_k": 5},
            headers=self.headers,
            timeout=(5, 30),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"memory query failed: {response.status_code} - {response.text[:200]}"
                )

    @task(2)
    def rag_hybrid_search(self):
        payload = {"query": "supremeai load test hybrid search probe", "top_k": 5}
        with self.client.post(
            "/api/v1/rag/hybrid-search",
            json=payload,
            headers=self.headers,
            timeout=(5, 30),
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"hybrid-search failed: {response.status_code} - {response.text[:200]}"
                )

    @task(1)
    def upload_attachment(self):
        # POST /api/chat/upload/ — multipart field 'file' (binary image, max 10MB)।
        # multipart রিকোয়েস্টে Content-Type হাতে সেট করা যাবে না (boundary)।
        upload_headers = _auth_headers(self.auth_token)
        with self.client.post(
            "/api/chat/upload/",
            files={"file": ("probe.png", _PNG_1X1_BYTES, "image/png")},
            headers=upload_headers,
            timeout=(5, 30),
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            else:
                response.failure(f"upload failed: {response.status_code} - {response.text[:200]}")


class TaskAgentUser(_BaseSupremeAIUser):
    """পার্সোনা ৩ (১০%): ব্যাকগ্রাউন্ড টাস্ক/এজেন্ট এক্সিকিউশন ট্রিগার।

    POST /api/task/execute (TaskRequest: task + task_type) এবং SSE কিপঅ্যালাইভ হোল্ড
    (GET /api/task/stream — পাথ প্যারামিটার নেই)। ব্রাউজার-সেশন স্পন ঐচ্ছিক
    (LOAD_TEST_INCLUDE_BROWSER=true হলেই) কারণ প্রতিটি কল সার্ভারে আসল
    chromium প্রসেস তৈরি করে।
    """

    weight = 1

    @task(3)
    def execute_task(self):
        payload = {
            "task": "load-test agent ping: summarize the current queue depth",
            "task_type": "general",
        }
        with self.client.post(
            "/api/task/execute",
            json=payload,
            headers=self.headers,
            timeout=(5, 45),
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201, 202):
                response.success()
            else:
                response.failure(
                    f"task/execute failed: {response.status_code} - {response.text[:200]}"
                )

    @task(2)
    def submit_durable_task(self):
        # POST /api/v1/tasks — TaskSubmission {goal: str}
        payload = {"goal": "load-test durable task: health-check ping"}
        with self.client.post(
            "/api/v1/tasks",
            json=payload,
            headers=self.headers,
            timeout=(5, 30),
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201, 202):
                response.success()
            else:
                response.failure(f"v1/tasks failed: {response.status_code} - {response.text[:200]}")

    @task(2)
    def sse_stream_hold(self):
        """SSE কানেকশন হোল্ড — GET /api/task/stream (keepalive, পাথ প্যারাম নেই)।

        সর্বোচ্চ ২০ সেকেন্ড ধরে কানেকশন খোলা রাখা হয় (মেমরি-লিক গার্ড)।
        """
        start_time = time.time()
        try:
            with self.client.get(
                "/api/task/stream",
                headers=self.headers,
                stream=True,
                timeout=(5, 45),
                catch_response=True,
            ) as sse_response:
                if sse_response.status_code != 200:
                    sse_response.failure(f"SSE gate blocked: {sse_response.status_code}")
                    return
                for _line in sse_response.iter_lines():
                    if time.time() - start_time > 20.0:
                        break
                sse_response.success()
        except Exception as e:
            events.request.fire(
                request_type="SSE_STREAM",
                name="/api/task/stream",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=e,
            )

    @task(1)
    def browser_session_spawn(self):
        """ঐচ্ছিক: ব্রাউজার অটোমেশন সেশন স্পন — ডিফল্টে বন্ধ।"""
        if not _INCLUDE_BROWSER_SESSIONS:
            return
        payload = {"label": "loadtest browser session"}
        with self.client.post(
            "/api/browser/automation/sessions",
            json=payload,
            headers=self.headers,
            timeout=(5, 45),
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            else:
                response.failure(
                    f"browser session failed: {response.status_code} - {response.text[:200]}"
                )
