# backend/tests/security/test_adversarial_corpus_regression.py
"""অ্যাডভারসারিয়াল কর্পাস রেগ্রেশন — ৩-স্তর টেস্টিং প্ল্যান Tier-2 (Phase 2)।

fixtures/adversarial_corpus.py-এর ৩২টি কেস pre_flight_scan (public API)
দিয়ে চালিয়ে:
- expect="blocked" কেসগুলো allowed=False হতেই হবে (জেলব্রেক/এক্সট্রাকশন/কোড);
- expect="allowed" কেসগুলো allowed=True হতেই হবে (false-positive গার্ড);
- expect="no_crash" কেসগুলো exception ছাড়া রায় দিতে হবে (হিউজ-কনটেক্সট)।

CI-safe: কোনো LLM/নেটওয়ার্ক নেই — pre_flight_scan-এর লোকাল প্যাটার্ন পথ।
"""

from __future__ import annotations

import pytest

from core.security.protection.prompt_firewall import pre_flight_scan
from tests.security.fixtures.adversarial_corpus import (
    ADVERSARIAL_CORPUS,
    cases_by_expect,
    corpus_ids,
)

pytestmark = pytest.mark.security


@pytest.mark.parametrize("case", ADVERSARIAL_CORPUS, ids=corpus_ids())
async def test_corpus_case_verdict(case):
    """Given: কর্পাসের একটি কেস এবং তার প্রত্যাশিত রায়।
    When: pre_flight_scan(content) চালানো হলে।
    Then: প্রত্যাশা অনুযায়ী blocked/allowed — no_crash হলে শুধু বেঁচে থাকা।
    """
    result = await pre_flight_scan(case.content)

    assert isinstance(result, dict), f"রায় dict নয়: {type(result)}"
    assert "allowed" in result, f"'allowed' কী নেই: {result}"

    if case.expect == "blocked":
        assert result["allowed"] is False, (
            f"[{case.case_id}] ব্লক হওয়ার কথা ছিল কিন্তু পাস হয়েছে "
            f"({case.category}): {case.content[:80]!r} → {result}"
        )
    elif case.expect == "allowed":
        assert result["allowed"] is True, (
            f"[{case.case_id}] false-positive — নিরীহ ইনপুট ব্লক হয়েছে "
            f"({case.category}): {case.content[:80]!r} → {result}"
        )
    # expect == "no_crash": উপরের await নিজেই প্রমাণ — exception হলে টেস্ট ফেল


class TestCorpusShape:
    def test_corpus_size_meets_plan_minimum(self):
        """Given: পরিকল্পনার ন্যূনতম ২০টি কেসের প্রয়োজন।
        When: কর্পাস গণনা করলে।
        Then: কমপক্ষে ২০টি কেস আছে (বাস্তবে ৩২)।
        """
        assert len(ADVERSARIAL_CORPUS) >= 20

    def test_corpus_covers_required_categories(self):
        """Given: পরিকল্পনার বাধ্যতামূলক ক্যাটাগরি।
        When: ক্যাটাগরির সেট সংগ্রহ করলে।
        Then: jailbreak, prompt_injection, sensitive_extraction, malicious_code,
        edge_case, huge_context, benign — সবই উপস্থিত।
        """
        categories = {c.category for c in ADVERSARIAL_CORPUS}
        required = {
            "jailbreak",
            "prompt_injection",
            "sensitive_extraction",
            "malicious_code",
            "edge_case",
            "huge_context",
            "benign",
        }
        missing = required - categories
        assert not missing, f"অনুপস্থিত ক্যাটাগরি: {missing}"

    def test_huge_context_case_is_really_20k_words(self):
        """Given: হিউজ-কনটেক্সট কেস।
        When: শব্দ গণনা করলে।
        Then: সত্যিই ~২০ হাজার শব্দ — ডকুমেন্টেড দাবির সৎ যাচাই।
        """
        huge = next(c for c in ADVERSARIAL_CORPUS if c.category == "huge_context")
        word_count = len(huge.content.split())
        assert word_count >= 19000, f"হিউজ-কেসটি আসলে ছোট: {word_count} শব্দ"

    def test_blocked_expectations_only_for_attack_categories(self):
        """Given: expect="blocked" কেসগুলো।
        When: ক্যাটাগরি পরীক্ষা করলে।
        Then: শুধুমাত্র আক্রমণ-ক্যাটাগরি blocked প্রত্যাশা বহন করে।
        """
        attack_categories = {"jailbreak", "prompt_injection", "sensitive_extraction", "malicious_code"}
        for case in cases_by_expect("blocked"):
            assert case.category in attack_categories, (
                f"[{case.case_id}] আক্রমণ-ক্যাটাগরি ছাড়া blocked-প্রত্যাশা সন্দেহজনক"
            )

    async def test_all_blocked_cases_fail_fast_locally(self):
        """Given: সব blocked-প্রত্যাশিত কেস।
        When: এক ব্যাচে চালালে।
        Then: প্রতিটিই লোকাল প্যাটার্নে ধরা পড়ে (LLM ছাড়াই fail-fast)।
        """
        for case in cases_by_expect("blocked"):
            result = await pre_flight_scan(case.content)
            assert result["allowed"] is False, (
                f"[{case.case_id}] লোকাল fail-fast পথ ধরেনি: {result}"
            )
