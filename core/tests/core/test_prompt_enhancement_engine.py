"""
Unit Tests for PromptEnhancementEngine (প্রম্পট উন্নয়ন ও স্টেলথ টেস্ট)
"""

import pytest

from core.prompt_enhancement_engine import (
    EnhancementContext,
    EnhancementMode,
    PromptEnhancementEngine,
    default_enhancer,
)


def test_stealth_chat_strips_meta_leaks_and_keeps_direct_flow():
    """
    বাংলা মন্তব্য: বাইরের প্রম্পট জেনারেটরের মেটা-লাইন ('Copy this to your AI...') মুছে খাঁটি হিউম্যান প্রশ্ন রাখা।
    """
    engine = PromptEnhancementEngine(rng_seed=42)
    raw_prompt = (
        "Copy this prompt to your desired AI's chat:\n"
        "Write a fastapi middleware to log requests without latency."
    )
    result = engine.enhance(raw_prompt, mode=EnhancementMode.STEALTH_CHAT)

    assert result.original_prompt == raw_prompt
    assert "copy this" not in result.enhanced_prompt.lower()
    assert result.enhanced_prompt == "Write a fastapi middleware to log requests without latency."
    assert "stripped_meta_generator_watermarks" in result.applied_tricks
    assert "organic_human_direct_flow" in result.applied_tricks


def test_stealth_chat_strips_unnatural_bot_pasting_line():
    """
    বাংলা মন্তব্য: 'Pasting this prompt from another workspace:' এর মতো কৃত্রিম বট টেক্সট মুছে ফেলা।
    """
    engine = PromptEnhancementEngine(rng_seed=42)
    raw = "Pasting this prompt from another workspace:\nBuild a user profile view."
    res = engine.enhance(raw, mode=EnhancementMode.STEALTH_CHAT)
    assert "pasting this prompt" not in res.enhanced_prompt.lower()
    assert res.enhanced_prompt == "Build a user profile view."
    assert "stripped_meta_generator_watermarks" in res.applied_tricks


def test_stealth_chat_strips_robotic_patterns():
    """
    বাংলা মন্তব্য: রোবটিক প্রিফিক্স স্বয়ংক্রিয়ভাবে ক্লিন করে কিনা যাচাই।
    """
    engine = PromptEnhancementEngine(rng_seed=123)
    robotic_prompt = (
        "You are an expert software engineer.\n"
        "Your task is to: fix the redis connection pool issue."
    )
    result = engine.enhance(robotic_prompt, mode=EnhancementMode.STEALTH_CHAT)

    assert "stripped_robotic_prefix" in result.applied_tricks
    assert "You are an expert" not in result.enhanced_prompt
    assert "Your task is to:" not in result.enhanced_prompt
    assert "fix the redis connection pool issue." in result.enhanced_prompt


def test_ui_sparkle_enhancement_with_context():
    """
    বাংলা মন্তব্য: UI-এর বাটন ক্লিক মোডে ফাইল এবং সিলেক্টেড কোড কনটেক্সট যুক্ত হয় কিনা।
    """
    engine = PromptEnhancementEngine()
    context = EnhancementContext(
        current_file_path="backend/core/cache.py",
        selected_code="def get_cache(): pass",
        language="python",
    )
    result = engine.enhance(
        "Optimize this function", mode=EnhancementMode.ENHANCE_UI_CLICK, context=context
    )

    assert "backend/core/cache.py" in result.enhanced_prompt
    assert "def get_cache(): pass" in result.enhanced_prompt
    assert "python" in result.enhanced_prompt
    assert "sparkle_button_enrichment" in result.applied_tricks


def test_dev_api_mode():
    """
    বাংলা মন্তব্য: ডেভেলপার এপিআই মোড প্রম্পট ফরম্যাট ঠিক রাখে কিনা।
    """
    engine = PromptEnhancementEngine()
    context = EnhancementContext(user_intent="refactor")
    result = engine.enhance("Make this async", mode=EnhancementMode.DEV_API, context=context)

    assert "[Intent: refactor]" in result.enhanced_prompt
    assert "Make this async" in result.enhanced_prompt


def test_empty_prompt():
    """
    বাংলা মন্তব্য: ফাঁকা প্রম্পট দিলে ক্র্যাশ না করে নিরাপদে রিটার্ন করে কিনা।
    """
    result = default_enhancer.enhance("   ", mode=EnhancementMode.STEALTH_CHAT)
    assert result.enhanced_prompt == "   "
    assert "empty_prompt_noop" in result.applied_tricks


def test_prompt_enhance_api_endpoint():
    """
    বাংলা মন্তব্য: FastAPI রাউট /v1/prompt/enhance ঠিকমতো কাজ করে কিনা যাচাই।
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.api.routes.web_ai_proxy import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/v1/prompt/enhance",
        json={
            "prompt": "Fix memory leak in websocket loop",
            "mode": "stealth_chat",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["original_prompt"] == "Fix memory leak in websocket loop"
    assert "organic_human_direct_flow" in data["applied_tricks"]
    assert data["enhanced_prompt"] == "Fix memory leak in websocket loop"


def test_account_session_thread_lifecycle():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    অ্যাকাউন্ট থ্রেড লাইফসাইকেল যাচাই:
    - প্রথম ৬টি টার্নে একই থ্রেড আইডি থাকবে (স্প্যামিং বন্ধ)
    - ৭ম টার্নে নতুন থ্রেড আইডিতে সুইচ করবে (হিস্ট্রি ব্লোট বন্ধ)
    """
    from core.web_ai_session_bridge import AccountSession

    acc = AccountSession(
        service="claude",
        account_id="claude-acc-1",
        token="tok_123",
        max_thread_turns=6,
    )

    # টার্ন ১: নতুন থ্রেড শুরু
    tid1, is_new1 = acc.get_or_rotate_thread_id()
    assert is_new1 is True
    assert tid1 is not None

    # টার্ন ২ থেকে ৬: একই থ্রেড রিইউজ হবে
    for turn in range(2, 7):
        tid, is_new = acc.get_or_rotate_thread_id()
        assert is_new is False
        assert tid == tid1
        assert acc.thread_turn_count == turn

    # টার্ন ৭: ম্যাক্স টার্ন এক্সিড হওয়ায় নতুন থ্রেড রোটেশন
    tid7, is_new7 = acc.get_or_rotate_thread_id()
    assert is_new7 is True
    assert tid7 != tid1
    assert acc.thread_turn_count == 1


@pytest.mark.asyncio
async def test_account_concurrency_lock():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    পার-অ্যাকাউন্ট কনকারেন্সি লক যাচাই:
    একই অ্যাকাউন্টে সমান্তরালে ১টির বেশি কাজ যেতে পারবে না।
    """
    from core.web_ai_session_bridge import AccountSession

    acc = AccountSession(service="claude", account_id="acc-test", token="tok")

    assert not acc._lock.locked()

    async with acc._lock:
        assert acc._lock.locked()

    assert not acc._lock.locked()


def test_dual_ai_conductor_mode():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    DUAL_AI_CONDUCTOR মোড যাচাই:
    ১. CONDUCTOR_HEADER_VARIANTS-এর যেকোনো একটি অর্গানিক হেডার দিয়ে শুরু হবে।
    ২. Autonomous Execution Agent / Implementation Brief ডিরেক্টিভ থাকবে।
    ৩. আসল টাস্কটি প্রম্পটে নিখুঁতভাবে অন্তর্ভুক্ত থাকবে।
    """
    engine = PromptEnhancementEngine(rng_seed=42)
    task = "Build a zero-latency memory cache middleware in FastAPI."
    result = engine.enhance(task, mode=EnhancementMode.DUAL_AI_CONDUCTOR)

    assert any(
        h in result.enhanced_prompt for h in PromptEnhancementEngine.CONDUCTOR_HEADER_VARIANTS
    )
    assert task in result.enhanced_prompt
    assert "dual_ai_conductor_proven_human" in result.applied_tricks
    assert "behavioral_style_entropy" in result.applied_tricks


def test_dual_ai_conductor_random_behavior_variation():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    বিহেভিয়ার র‍্যান্ডম ভ্যারিয়েশন যাচাই (Behavior Randomly Changes):
    একাধিকবার কল করলে সবসময় একই স্টাইল বা হেডার তৈরি হবে না, বরং ডায়নামিক এন্ট্রপি বজায় থাকবে।
    """
    engine = PromptEnhancementEngine()
    task = "Implement robust retry with circuit breaker"

    seen_headers = set()
    seen_outputs = set()

    for _ in range(25):
        res = engine.enhance(task, mode=EnhancementMode.DUAL_AI_CONDUCTOR)
        matched_header = False
        for h in PromptEnhancementEngine.CONDUCTOR_HEADER_VARIANTS:
            if h and res.enhanced_prompt.startswith(h):
                seen_headers.add(h)
                matched_header = True
                break
        if not matched_header:
            seen_headers.add("<direct_no_header>")
        seen_outputs.add(res.enhanced_prompt)

    # প্রমাণ: একাধিক ভিন্ন হেডার এবং ভিন্ন ভিন্ন স্টাইল আউটপুট তৈরি হয়েছে (স্থির বা রোবটিক নয়)
    assert len(seen_headers) > 1, f"Expected varied headers, got: {seen_headers}"
    assert len(seen_outputs) > 2, (
        f"Expected varied styles, got {len(seen_outputs)} distinct outputs"
    )


def test_dual_ai_conductor_with_coding_context():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    কোডিং কনটেক্সট থাকলে নির্দিষ্ট এনভায়রনমেন্ট রুলস (ইউনিট টেস্ট চালানো) যুক্ত হওয়া যাচাই।
    """
    engine = PromptEnhancementEngine(rng_seed=99)
    context = EnhancementContext(language="python", current_file_path="backend/core/cache.py")
    result = engine.enhance(
        "Refactor cache pool", mode=EnhancementMode.DUAL_AI_CONDUCTOR, context=context
    )

    assert any(
        h in result.enhanced_prompt for h in PromptEnhancementEngine.CONDUCTOR_HEADER_VARIANTS
    )
    assert "ENVIRONMENT DIRECTIVE (Coding Agent):" in result.enhanced_prompt
    assert "run unit tests or syntax checks after every edit" in result.enhanced_prompt
    assert "coding_agent_env_directive" in result.applied_tricks


def test_is_banglish_or_bengali_detection():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    বাংলিশ ও বাংলা ল্যাঙ্গুয়েজ ডিটেকশন যাচাই:
    - ইংলিশ অ্যালফাবেটে বাংলা (Banglish): "bhai eta koro", "ami ekta cache middleware banate chai"
    - খাঁটি বাংলা ইউনিকোড: "এই কোডটি ঠিক করুন"
    """
    assert PromptEnhancementEngine.is_banglish_or_bengali("bhai eta koro and check error") is True
    assert (
        PromptEnhancementEngine.is_banglish_or_bengali(
            "ami ekta fast redis pool implement korte chai"
        )
        is True
    )
    assert PromptEnhancementEngine.is_banglish_or_bengali("এই কোডটি ঠিক করুন") is True
    assert PromptEnhancementEngine.is_banglish_or_bengali("pure textbook english prompt") is False


def test_banglish_prompt_regional_stealth():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    বাংলিশ প্রম্পটে regional_banglish_human_stealth ট্রিক যুক্ত হওয়া এবং মূল ভাষা সংরক্ষিত থাকা।
    """
    engine = PromptEnhancementEngine()
    prompt = "fastapi te memory leak hocche, bhai eta fix koro"
    res = engine.enhance(prompt, mode=EnhancementMode.STEALTH_CHAT)

    assert "regional_banglish_human_stealth" in res.applied_tricks
    assert "fastapi te memory leak hocche, bhai eta fix koro" in res.enhanced_prompt


def test_regional_geo_locale_headers():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    বাংলাদেশ আইপির সাথে সামঞ্জস্যপূর্ণ ব্রাউজার হেডার ও টাইমজোন যাচাই।
    """
    from core.web_ai_session_bridge import WebAISessionBridge

    bridge = WebAISessionBridge()
    headers = bridge._get_headers("claude")
    assert "bn-BD" in headers["Accept-Language"]
    assert "en-US" in headers["Accept-Language"]
