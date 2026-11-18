"""Generate Human Behavior + Intent/Action Routing SFT dataset (JSONL) for Kaggle QLoRA."""

from __future__ import annotations

import json
from pathlib import Path

SYSTEM_PROMPT = (
    "You are SupremeAI Tiny Brain. Analyze the user's message (and short context) "
    "and output ONLY valid JSON with keys: intent, user_tone, capability_tier, "
    "dispatch_mode, optimized_prompt, tools_needed."
)

SEED_EXAMPLES: list[tuple[str, dict]] = [
    (
        "hi kemon acho?",
        {
            "intent": "general_chat",
            "user_tone": "casual",
            "capability_tier": "local_reply",
            "dispatch_mode": "direct_prompt",
            "optimized_prompt": "Reply warmly in Bangla to a casual greeting.",
            "tools_needed": [],
        },
    ),
    (
        "bhai server down hoye gese check koro",
        {
            "intent": "system_action",
            "user_tone": "urgent",
            "capability_tier": "mcp_tower",
            "dispatch_mode": "tool_call",
            "optimized_prompt": "Check server health and recent error logs immediately.",
            "tools_needed": ["health_check", "render_logs"],
        },
    ),
    (
        "aita kaj kore na keno? [Context: user was testing /rotate endpoint]",
        {
            "intent": "code_debug",
            "user_tone": "confused",
            "capability_tier": "deep_coding",
            "dispatch_mode": "rag_plus_prompt",
            "optimized_prompt": "Debug why the /rotate endpoint is failing based on recent context.",
            "tools_needed": ["code_search"],
        },
    ),
    (
        "write a fast python async function to retry http 429",
        {
            "intent": "code_debug",
            "user_tone": "technical",
            "capability_tier": "deep_coding",
            "dispatch_mode": "direct_prompt",
            "optimized_prompt": "Write a clean Python async retry helper with exponential backoff for HTTP 429.",
            "tools_needed": [],
        },
    ),
    (
        "ajker weather ta ki?",
        {
            "intent": "research",
            "user_tone": "casual",
            "capability_tier": "fast_chat",
            "dispatch_mode": "tool_call",
            "optimized_prompt": "Look up current weather information.",
            "tools_needed": ["web_search"],
        },
    ),
]


def generate_jsonl(output_path: Path) -> int:
    """Write ChatML-formatted JSONL training data and return sample count."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for user_text, target in SEED_EXAMPLES:
            record = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
                ]
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(SEED_EXAMPLES)


if __name__ == "__main__":
    out = Path("core/scripts/data/tiny_brain_seed.jsonl")
    count = generate_jsonl(out)
    print(f"Generated {count} training examples -> {out}")
