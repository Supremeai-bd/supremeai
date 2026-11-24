"""core.agent_tool_specs — OpenAI-style declarations for the governed tool registry.

বাংলা: চ্যাট কী কী টুল *দেখতে* পায় তার একক ঘোষণা (declaration), নির্বাহ নয়।
প্রকৃত নির্বাহ ``core.tool_loop``-এ থাকে — এই ফাইলটা কেবল নাম, বর্ণনা ও
প্যারামিটার-স্কিমা ধরে, যাতে মডেল OpenAI ``tools`` আকৃতিতে কল করতে পারে।

কেন আলাদা টেবিল (docstring থেকে স্কিমা তৈরি নয়): ফাংশন-সিগনেচার থেকে
অটো-স্কিমা তৈরি করলে ডিফল্ট/অপশনাল পার্থক্য নীরবে বদলে যেতে পারে, আর
``**kwargs``-জাতীয় টুল ভুল স্কিমা দিত। এখানে হাতে-লেখা স্কিমা, আর
``tests/test_agent_tool_surface.py`` রেজিস্ট্রির সাথে হুবহু মিলিয়ে দেখে
(নতুন গভর্নড টুল যোগ হলে spec ছাড়া CI ফেল করবে)।

গুরুত্বপূর্ণ সীমা: ব্রাউজার-অটোমেশনের রিড টুলগুলো (open, inspect, screenshot) R0 হিসেবে
সরাসরি অনুমোদিত, তবে স্টেট-পরিবর্তনকারী টুলগুলো (click, fill) R2 হিসেবে মানব-অনুমোদন
(HITL TaskApprovalCard) সাপেক্ষ।
"""

from __future__ import annotations

from typing import Any

#: OpenAI ``tools`` entries for every governed tool that can *ever* run from chat.
#: ``policy_name`` must match a key in ``core.mcp_policy.TOOL_PROVIDER_ACTION``.
TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "search_database",
        "description": (
            "Search the workspace database (tasks, messages, projects) with a "
            "case-insensitive text query. Read-only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to look for. Keep it short (a few words).",
                    "minLength": 1,
                    "maxLength": 200,
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_system_health",
        "description": "Read current system health status (service availability). Read-only.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "cot_verify_math",
        "description": (
            "Verify a claimed mathematical result symbolically (deterministic, "
            "no side effects). Use before quoting any computed number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The expression to evaluate, e.g. '2**0.5'.",
                    "minLength": 1,
                    "maxLength": 500,
                },
                "claimed_result": {
                    "type": "string",
                    "description": "The result being checked, as text.",
                    "minLength": 1,
                    "maxLength": 200,
                },
            },
            "required": ["expression", "claimed_result"],
            "additionalProperties": False,
        },
    },
    {
        "name": "execute_python_code",
        "description": (
            "Run sandboxed Python. Declared for completeness only: policy rates it "
            "R5 (critical), so it never executes without human approval, and chat "
            "has no approval hook yet — the manifest reports it as unavailable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source to execute.",
                    "minLength": 1,
                    "maxLength": 20_000,
                }
            },
            "required": ["code"],
            "additionalProperties": False,
        },
    },
    {
        "name": "browser_open",
        "description": "Open a web page in the autonomous executive browser session. Read-only (R0).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to open in the browser.",
                    "minLength": 1,
                    "maxLength": 2048,
                }
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "browser_inspect",
        "description": "Inspect text content or specific element on the current browser page. Read-only (R0).",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector to inspect specific element text.",
                    "maxLength": 500,
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "browser_screenshot",
        "description": "Capture a screenshot of the current browser page. Read-only (R0).",
        "parameters": {
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": "Whether to capture the entire scrollable page height.",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "browser_verify_result",
        "description": (
            "Verify post-condition proof (URL substring or visible CSS selector) "
            "on the active browser page before claiming task completion. Read-only (R0)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expected_selector_or_url": {
                    "type": "string",
                    "description": "Expected URL substring or CSS selector that proves the step succeeded.",
                    "minLength": 1,
                    "maxLength": 500,
                }
            },
            "required": ["expected_selector_or_url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "browser_click",
        "description": "Click an element matching CSS selector on the current page. State-changing (R2) — requires human approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the button/link/element to click.",
                    "minLength": 1,
                    "maxLength": 500,
                }
            },
            "required": ["selector"],
            "additionalProperties": False,
        },
    },
    {
        "name": "browser_fill",
        "description": "Fill a form input field matching CSS selector on the current page. State-changing (R2) — requires human approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the input field to fill.",
                    "minLength": 1,
                    "maxLength": 500,
                },
                "value": {
                    "type": "string",
                    "description": "Text value to enter into the field.",
                    "maxLength": 10000,
                },
            },
            "required": ["selector", "value"],
            "additionalProperties": False,
        },
    },
)

#: Fast lookup: tool name -> spec.
SPECS_BY_NAME: dict[str, dict[str, Any]] = {spec["name"]: spec for spec in TOOL_SPECS}


def openai_tool_entry(name: str) -> dict[str, Any] | None:
    """Return ``{"type": "function", "function": {...}}`` for one tool, or ``None``."""
    spec = SPECS_BY_NAME.get(name)
    if spec is None:
        return None
    return {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["parameters"],
        },
    }
