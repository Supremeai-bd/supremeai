"""Regression tests for SupremeAI Security Guard secret patterns.

ব্যাসিক ইউনিট টেস্ট — SECRET_PATTERNS রেজেক্সগুলো আসল সিক্রেট শনাক্ত করে এবং
নিরীহ টেক্সট মিস করে কিনা তা যাচাই করে।
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from security_guard import SECRET_PATTERNS  # noqa: E402


def _match_any(text: str) -> bool:
    return any(re.search(p, text) for p in SECRET_PATTERNS.values())


def test_detects_real_secrets():
    samples = [
        "sk-" + "a" * 48,
        "rnd_" + "b" * 32,
        "sk_live_" + "c" * 24,
        'AKIA' + "D" * 16,
        '{"type": "service_account", "project_id": "x"}',
        "Authorization: Bearer " + "e" * 40,
        "sk-sup-ABCDEFGHIJKLMNOPQRST",
    ]
    for s in samples:
        assert _match_any(s), f"Expected secret detection for: {s!r}"


def test_ignores_benign_text():
    samples = [
        "const url = 'https://api.supremeai.com/v1';",
        "const timeout = 10000;",
        "export const apiBridge = new SupremeExtensionBridge();",
        "sessionId = vscode-${Date.now()};",
    ]
    for s in samples:
        assert not _match_any(s), f"False positive for benign text: {s!r}"


if __name__ == "__main__":
    test_detects_real_secrets()
    test_ignores_benign_text()
    print("ALL SECURITY GUARD TESTS PASSED")
