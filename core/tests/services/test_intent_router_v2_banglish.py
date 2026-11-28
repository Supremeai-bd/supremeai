"""IntentRouterV2 regex fallback-এ Banglish routing যাচাই (#intelligence).

বাংলা মন্তব্য: LLM gatekeeper বন্ধ/টাইমআউট হলে regex fallback-ই শেষ ভরসা।
সেখানে বাংলা/Banglish কীওয়ার্ড ছিল না — ফলে বাংলা-ভাষী ব্যবহারকারীর
code/video/deploy/research অনুরোধ সব "chat" হয়ে যেত। এই টেস্ট সেই চুক্তি বাঁধে।
"""

import pytest

from core.intent_router_v2 import intent_router_v2


@pytest.fixture(autouse=True)
def _force_regex_mode(monkeypatch):
    monkeypatch.setenv("INTENT_ROUTER_MODE", "regex")


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("code likho ekta function", "code_generate"),
        ("ei prompt theke ekta function banao", "code_generate"),
        ("video edit koro", "video_edit"),
        ("video edit koro trim", "video_edit"),
        ("settings change koro", "settings_change"),
        ("theme bodlao", "settings_change"),
        ("deploy kore dao", "deploy"),
        ("publish koro live dao", "deploy"),
        ("current situation of Bangladesh jano", "research"),
        ("editor dekhao full", "ide_open"),
    ],
)
def test_banglish_prompts_route_correctly_without_llm(prompt, expected):
    action = intent_router_v2._route_regex(prompt)
    assert action.action_type == expected, f"{prompt!r} → {action.action_type}, expected {expected}"


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("hello kemon acho", "chat"),
        ("thanks bro", "chat"),
        ("ki khobor", "chat"),
    ],
)
def test_banglish_smalltalk_stays_chat(prompt, expected):
    # বাংলা মন্তব্য: over-routing বাদ — সাধারণ কথা "research" নয়, chat-ই হবে।
    action = intent_router_v2._route_regex(prompt)
    assert action.action_type == expected, f"{prompt!r} → {action.action_type}, expected {expected}"
