"""
SupremeAI Core Agent Tools
বাংলা মন্তব্য: এই মডিউলে AI এজেন্টের তিনটি মূল টুল রয়েছে।
আগে এগুলো সম্পূর্ণ mock/hardcoded ছিল — এখন সম্পূর্ণ production-ready রিয়েল ইমপ্লিমেন্টেশন।
"""

import os
from typing import Any

import httpx

from core.config import settings
from core.monitoring.logging_config import logger


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ১. Database Search Tool — Supabase REST API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def search_database(query: str) -> str:
    """
    Supabase PostgreSQL-এ full-text search করে।
    বাংলা মন্তব্য: আগে hardcoded "Found 3 matching records" রিটার্ন করা হতো।
    এখন Supabase REST API-এ আসল কোয়েরি পাঠানো হয় এবং সত্যিকারের রেজাল্ট ফেরত দেওয়া হয়।
    Use: ইউজার historical tasks, project records বা user data জিজ্ঞেস করলে।
    """
    logger.info(f"🔍 [TOOL] Searching Supabase for: {query!r}")

    supabase_url = settings.supabase_url
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not supabase_key:
        logger.warning("Supabase credentials missing — cannot perform real DB search.")
        return "Database search unavailable: SUPABASE_URL/SUPABASE_KEY not configured."

    # বাংলা মন্তব্য: Supabase REST ilike দিয়ে case-insensitive full-text match
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    results: list[dict[str, Any]] = []
    tables_to_search = ["tasks", "messages", "projects"]

    async with httpx.AsyncClient(timeout=15.0) as client:
        for table in tables_to_search:
            try:
                url = f"{supabase_url}/rest/v1/{table}"
                params = {
                    "select": "*",
                    "or": f"(title.ilike.*{query}*,description.ilike.*{query}*,content.ilike.*{query}*)",
                    "limit": "10",
                }
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        results.extend([{"table": table, **row} for row in data[:5]])
                elif resp.status_code == 404:
                    # বাংলা মন্তব্য: টেবিল না থাকলে শান্তভাবে এড়িয়ে যাও
                    pass
                else:
                    logger.debug(f"Table '{table}' search returned HTTP {resp.status_code}")
            except httpx.RequestError as exc:
                logger.warning(f"Supabase search error for table '{table}': {exc}")

    if not results:
        return f"No records found matching '{query}' in database."

    # বাংলা মন্তব্য: রেজাল্ট ফরম্যাট করে স্ট্রিং হিসেবে রিটার্ন
    summary_lines = [f"Found {len(results)} record(s) matching '{query}':"]
    for i, row in enumerate(results[:10], 1):
        table_name = row.pop("table", "unknown")
        row_id = row.get("id", row.get("uuid", "N/A"))
        title = row.get("title", row.get("name", row.get("content", str(row))[:80]))
        summary_lines.append(f"  {i}. [{table_name}] ID={row_id}: {title}")

    return "\n".join(summary_lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ২. System Health Tool — psutil + Redis + DB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def check_system_health() -> str:
    """
    রিয়েল সিস্টেম স্বাস্থ্য পরীক্ষা করে: CPU, RAM, Redis, Supabase DB।
    বাংলা মন্তব্য: আগে hardcoded "CPU: 12%, RAM: 45%" রিটার্ন হতো।
    এখন psutil দিয়ে আসল CPU/RAM পড়া হয় এবং Redis ও DB ping করা হয়।
    Use: সিস্টেম স্ট্যাটাস, ডাউনটাইম বা পারফরম্যান্স সম্পর্কে জিজ্ঞেস করলে।
    """
    logger.info("🩺 [TOOL] Checking real system health...")
    health: dict[str, Any] = {}

    # ── CPU & RAM (psutil) ──────────────────────────
    try:
        import psutil

        cpu_pct = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        health["cpu_percent"] = cpu_pct
        health["ram_used_pct"] = mem.percent
        health["ram_available_gb"] = round(mem.available / (1024**3), 2)
        health["disk_used_pct"] = disk.percent
    except ImportError:
        health["cpu_percent"] = "psutil_not_installed"
        health["ram_used_pct"] = "psutil_not_installed"
    except Exception as exc:
        health["system_error"] = str(exc)

    # ── Redis Ping ──────────────────────────────────
    redis_url = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL", "")
    if redis_url:
        try:
            import redis as redis_lib

            r = redis_lib.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
            r.ping()
            health["redis"] = "ONLINE"
            info = r.info("memory")
            health["redis_used_memory_mb"] = round(info.get("used_memory", 0) / (1024**2), 2)
        except Exception as exc:
            health["redis"] = f"OFFLINE ({exc})"
    else:
        health["redis"] = "NOT_CONFIGURED"

    # ── Supabase DB Ping ────────────────────────────
    supabase_url = settings.supabase_url
    supabase_key = os.getenv("SUPABASE_KEY", "")
    if supabase_url and supabase_key:
        try:
            resp = httpx.get(
                f"{supabase_url}/rest/v1/",
                headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
                timeout=5.0,
            )
            health["database"] = (
                "ONLINE" if resp.status_code < 500 else f"ERROR ({resp.status_code})"
            )
        except Exception as exc:
            health["database"] = f"OFFLINE ({exc})"
    else:
        health["database"] = "NOT_CONFIGURED"

    # ── Format output ───────────────────────────────
    redis_ok = health.get("redis") == "ONLINE"
    db_ok = "ONLINE" in str(health.get("database", ""))
    status = "ONLINE" if redis_ok and db_ok else "DEGRADED"

    lines = [
        f"System Status: {status}",
        f"CPU: {health.get('cpu_percent', 'N/A')}%",
        f"RAM Used: {health.get('ram_used_pct', 'N/A')}% (Available: {health.get('ram_available_gb', 'N/A')} GB)",
        f"Disk: {health.get('disk_used_pct', 'N/A')}% used",
        f"Redis: {health.get('redis', 'N/A')}",
        f"Database: {health.get('database', 'N/A')}",
    ]
    if "redis_used_memory_mb" in health:
        lines.append(f"Redis Memory: {health['redis_used_memory_mb']} MB")
    return " | ".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ৩. Execute Code Tool — Real DockerSandbox
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def execute_python_code(code: str) -> str:
    """
    DockerSandbox-এ নিরাপদভাবে Python code চালায়।
    বাংলা মন্তব্য: আগে hardcoded "Hello from SupremeAI Sandbox!" রিটার্ন হতো।
    এখন DockerSandbox.execute_command() delegate করা হয় — Docker না থাকলেও
    controlled local subprocess fallback আছে (dev/local env-এ)।
    Use: ইউজার explicitly code run বা complex math calculate করতে বললে।
    """
    logger.info(f"⚙️ [TOOL] Executing Python code in sandbox (length={len(code)} chars)")

    try:
        from core.tools.devops.docker_sandbox import DockerSandbox

        sandbox = DockerSandbox(image="python:3.11-slim")

        # Security Fix: Use run_secure() which writes code to a temp file and
        # mounts it read-only in Docker. This eliminates the command injection
        # risk of embedding LLM-generated code into a "python -c" shell string.
        result = sandbox.run_secure(code, timeout=30)

        if result.get("success"):
            output = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()
            mode = "simulated" if result.get("simulated") else "docker"
            response = f"[{mode.upper()}] Execution successful."
            if output:
                response += f"\nOutput:\n{output}"
            if stderr:
                response += f"\nStderr:\n{stderr}"
            return response
        else:
            err = result.get("error", "Unknown error")
            return f"Execution failed: {err}"

    except ImportError:
        logger.error("DockerSandbox not available — cannot execute code.")
        return "Code execution unavailable: DockerSandbox module not found."
    except Exception as exc:
        logger.error(f"Code execution error: {exc}")
        return f"Execution error: {exc}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# সব টুলের তালিকা — AI-কে দেওয়া হবে
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPREME_TOOLS = [search_database, check_system_health, execute_python_code]


# ── M09 P-G first-fleet (issue #453 Wave 4) ────────────────────────────────
# বাংলা: ৪৪ dormant টুলের মধ্যে প্রথম জাগরণ — cot_reasoner-এর সৎ-
# deterministic অংশ (sympy যাচাই)। কোড-নির্বাহ নয়, পার্শ্বপ্রতিক্রিয়া-শূন্য
# গণনা — তাই নীতিতে R0। জাগরণ flag-gated: SUPREMEAI_TOOL_FLEET=false =
# আজকের আচরণ (registry-তে ৩টি বেস টুল)।
def cot_verify_math(expression: str, claimed_result: str) -> str:
    """Verify a claimed mathematical result symbolically (deterministic, R0).

    বাংলা: LLM-এর দাবি-করা গাণিতিক ফল sympy দিয়ে সত্য-যাচাই —
    hallucinated arithmetic ধরার governed প্রথম-ফ্লিট টুল।
    """
    from core.tools.code.cot_reasoner import verify_symbolic_math

    result = verify_symbolic_math(str(expression), str(claimed_result))
    verdict = "VERIFIED" if result.get("is_verified") else "REFUTED"
    return f"[{verdict}] {result}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ৪. Browser Automation Tools (Personal Executive — Owner-Scoped)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import contextvars

# বাংলা মন্তব্য: প্রতিটি টেন্যান্ট/ইউজারের ব্রাউজার সেশন কঠোরভাবে আইসোলেটেড থাকবে;
# গ্লোবাল শেয়ার্ড সেশন সম্পূর্ণ নিষিদ্ধ (ক্রস-টেন্যান্ট কুকি লিক প্রতিরোধ)।
CURRENT_TOOL_OWNER: contextvars.ContextVar[str] = contextvars.ContextVar(
    "CURRENT_TOOL_OWNER", default=""
)


def _require_browser_owner() -> str:
    """Resolve the caller's isolated browser owner_id, failing closed if absent."""
    owner = (CURRENT_TOOL_OWNER.get() or "").strip()
    if not owner or owner == "*":
        raise PermissionError(
            "Authenticated tenant/owner context is required for browser session isolation"
        )
    return f"agent_exec:{owner}"


async def _get_or_create_browser_session():
    """Retrieve the caller's isolated browser session or create one scoped to their tenant."""
    from core.browser_session_manager import session_manager

    owner_id = _require_browser_owner()
    snapshot = session_manager.snapshot()
    for s in snapshot:
        if s.get("owner_id") == owner_id:
            try:
                return await session_manager.get(s["id"], owner_id)
            except Exception as exc:
                logger.debug(f"[agent_tools] stale browser session {s.get('id')} skipped: {exc}")
    return await session_manager.create(owner_id, label="Autonomous Executive Browser")


async def browser_open(url: str) -> str:
    """Open a web page in the caller's isolated browser session (R0 safe read)."""
    # বাংলা মন্তব্য: ওনার-স্কোপড স্বয়ংক্রিয় ব্রাউজার সেশনে নিরাপদ URL পরিদর্শন (SSRF গার্ডসহ)
    from core.security import is_safe_url

    url_clean = (url or "").strip()
    if not url_clean:
        return "Error: URL is required"
    if not is_safe_url(url_clean):
        return f"Error: URL '{url_clean}' is blocked by security policy (SSRF/private IP protection)"
    try:
        session = await _get_or_create_browser_session()
        page = session.page
        resp = await page.goto(url_clean, timeout=20_000, wait_until="domcontentloaded")
        status = resp.status if resp else "unknown"
        title = await page.title()
        return f"Opened {url_clean} (HTTP {status}). Page title: {title!r}"
    except PermissionError as exc:
        return f"Browser session denied: {exc}"
    except Exception as exc:
        logger.warning(f"[agent_tools] browser_open failed: {exc}")
        return f"Browser open failed: {exc}"


async def browser_inspect(selector: str = "") -> str:
    """Inspect page text content or a specific element matching a CSS selector (R0 safe read)."""
    # বাংলা মন্তব্য: ব্রাউজারের বর্তমান পৃষ্ঠার কন্টেন্ট বা নির্দিষ্ট এলিমেন্ট পরিদর্শন এবং ক্যাপচা/ওটিপি শনাক্তকরণ
    try:
        session = await _get_or_create_browser_session()
        page = session.page
        sel = (selector or "").strip()
        if sel:
            locator = page.locator(sel)
            count = await locator.count()
            if count == 0:
                return f"No element matching selector '{sel}' found on current page ({page.url})."
            text = await locator.first.inner_text(timeout=5_000)
            return f"Element '{sel}' text (first of {count}):\n{text[:2000]}"
        content = await page.inner_text("body", timeout=5_000)
        title = await page.title()
        lowered = f"{title}\n{content[:1500]}".lower()
        if any(gate in lowered for gate in ("captcha", "recaptcha", "hcaptcha", "turnstile", "verify you are human", "enter otp", "verification code")):
            return (
                f"[USER_HANDOFF_REQUIRED: captcha_or_otp] Page '{title}' ({page.url}) "
                "requires human OTP/CAPTCHA verification. Automated bypass is prohibited."
            )
        return f"Page '{title}' ({page.url}) content preview:\n{content[:2000]}"
    except PermissionError as exc:
        return f"Browser session denied: {exc}"
    except Exception as exc:
        logger.warning(f"[agent_tools] browser_inspect failed: {exc}")
        return f"Browser inspect failed: {exc}"


async def browser_screenshot(full_page: bool = False) -> str:
    """Capture a screenshot of the current browser page (R0 safe read)."""
    # বাংলা মন্তব্য: ব্রাউজার পৃষ্ঠার পোস্ট-কন্ডিশন স্ক্রিনশট প্রমাণ ধারণ
    try:
        session = await _get_or_create_browser_session()
        page = session.page
        b64 = await page.screenshot(full_page=bool(full_page))
        return f"Screenshot captured successfully ({len(b64)} bytes) for {page.url}"
    except PermissionError as exc:
        return f"Browser session denied: {exc}"
    except Exception as exc:
        logger.warning(f"[agent_tools] browser_screenshot failed: {exc}")
        return f"Browser screenshot failed: {exc}"


async def browser_verify_result(expected_selector_or_url: str) -> str:
    """Verify post-condition proof (URL substring or visible DOM selector) before claiming completion."""
    # বাংলা মন্তব্য: কোনো ব্রাউজার টাস্ক সম্পন্ন দাবি করার আগে বাস্তব DOM/URL প্রমাণ যাচাই
    target = (expected_selector_or_url or "").strip()
    if not target:
        return "Error: expected_selector_or_url is required"
    try:
        session = await _get_or_create_browser_session()
        page = session.page
        current_url = str(page.url or "")
        if target in current_url:
            return f"[VERIFIED] Current URL '{current_url}' matches expected '{target}'."
        locator = page.locator(target)
        count = await locator.count()
        if count > 0 and await locator.first.is_visible():
            snippet = (await locator.first.inner_text(timeout=3_000)).strip()[:240]
            return f"[VERIFIED] Selector '{target}' is visible on '{current_url}': {snippet!r}"
        return f"[UNVERIFIED] Neither URL '{current_url}' nor visible DOM matched '{target}'."
    except PermissionError as exc:
        return f"Browser session denied: {exc}"
    except Exception as exc:
        logger.warning(f"[agent_tools] browser_verify_result failed: {exc}")
        return f"[UNVERIFIED] Verification failed: {exc}"


async def browser_click(selector: str) -> str:
    """Click an element on the current page (R2 write — requires HITL approval)."""
    # বাংলা মন্তব্য: ব্রাউজারে বাটন বা লিংক ক্লিক — স্টেট পরিবর্তনকারী অপারেশন
    sel = (selector or "").strip()
    if not sel:
        return "Error: selector is required to click an element"
    try:
        session = await _get_or_create_browser_session()
        page = session.page
        locator = page.locator(sel).first
        await locator.wait_for(state="visible", timeout=10_000)
        await locator.click(timeout=10_000)
        return f"Clicked element '{sel}' on {page.url}"
    except PermissionError as exc:
        return f"Browser session denied: {exc}"
    except Exception as exc:
        logger.warning(f"[agent_tools] browser_click failed: {exc}")
        return f"Browser click failed on '{sel}': {exc}"


async def browser_fill(selector: str, value: str) -> str:
    """Fill an input field on the current page (R2 write — requires HITL approval)."""
    # বাংলা মন্তব্য: ফর্ম ইনপুট ফিলাপ — স্টেট পরিবর্তনকারী অপারেশন
    sel = (selector or "").strip()
    if not sel:
        return "Error: selector is required"
    try:
        session = await _get_or_create_browser_session()
        page = session.page
        locator = page.locator(sel).first
        await locator.wait_for(state="visible", timeout=10_000)
        await locator.fill(str(value), timeout=10_000)
        return f"Filled element '{sel}' with value on {page.url}"
    except PermissionError as exc:
        return f"Browser session denied: {exc}"
    except Exception as exc:
        logger.warning(f"[agent_tools] browser_fill failed: {exc}")
        return f"Browser fill failed on '{sel}': {exc}"


FLEET_TOOLS = [
    cot_verify_math,
    browser_open,
    browser_inspect,
    browser_screenshot,
    browser_verify_result,
    browser_click,
    browser_fill,
]


def fleet_enabled() -> bool:
    """Flag-gate: ``SUPREMEAI_TOOL_FLEET=true`` হলেই কেবল সত্য (default OFF)।"""
    import os

    return os.environ.get("SUPREMEAI_TOOL_FLEET", "").strip().lower() == "true"


def governed_tools() -> list:
    """Flag-aware governed registry — base SUPREME_TOOLS + fleet (flag-on)।

    বাংলা: flag-off-এ রিটার্ন SUPREME_TOOLS-এর হুবহু প্রতিলিপি —
    আজকের আচরণ byte-সমতুল্য; অজানা অবস্থায় কোনো টুল নীরবে ঢোকে না।
    """
    tools_list = list(SUPREME_TOOLS)
    if fleet_enabled():
        tools_list.extend(FLEET_TOOLS)
    return tools_list
