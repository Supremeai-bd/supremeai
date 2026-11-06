# tests/test_smart_context_selector.py
# বাংলা মন্তব্য: Smart Context Selector (Issue #105) Pytest Suite
# scripts/agents/smart_context_selector.py-এর Layer 1-8 সিলেকশন এবং পলিসি ভেরিফিকেশন।

import pytest
import subprocess
import sys


def test_smart_context_selector_self_test():
    """Run the comprehensive self-test suite built into smart_context_selector."""
    result = subprocess.run(
        [sys.executable, "scripts/agents/smart_context_selector.py", "--self-test"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[PASS] tokens_used = 4650" in result.stdout
    assert "[PASS] determinism: same input ⇒ same assembly_id" in result.stdout
    assert "[PASS] L1 constitution included" in result.stdout
