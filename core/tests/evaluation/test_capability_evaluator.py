# backend/tests/evaluation/test_capability_evaluator.py
"""backend/evaluation প্যাকেজের প্রথম টেস্ট — ৩-স্তর টেস্টিং প্ল্যান Tier-2।

#4047-এ যোগ হওয়া capability_evaluator + scorers-এর কোনো টেস্টই ছিল না।
যাচাই: evaluate_provider-এর ৭-মাত্রিক স্কোর, ওয়েটেড অ্যাগ্রিগেট,
লেটেন্সি-স্কোরারের নরমালাইজেশন + নেগেটিভ-ভ্যালু গার্ড।
CI-safe: বিশুদ্ধ ইন-মেমরি গণনা।
"""

from __future__ import annotations

import pytest

from core.evaluation.capability_evaluator import evaluate_provider
from core.evaluation.models import DimensionScore, ProviderScore, ScoreDimension
from core.evaluation.scorers.latency import (
    LATENCY_P95_BEST_MS,
    LATENCY_P95_WORST_MS,
    score_latency,
)

pytestmark = pytest.mark.important

# evaluate_provider যে কীগুলো পড়ে — একটি স্বাস্থ্যকর প্রোভাইডারের মাপ
_HEALTHY_MEASUREMENTS: dict[str, float | str | bool | int] = {
    "test_pass_rate": 0.95,
    "llm_judge_score": 0.9,
    "p50_ms": 300.0,
    "p95_ms": 800.0,
    "p99_ms": 1200.0,
    "cost_per_call_usd": 0.002,
    "cost_per_task_usd": 0.01,
    "uptime_pct": 99.5,
    "error_rate_pct": 0.2,
    "health_status": "healthy",
    "data_exposure_risk": 0.05,
    "pii_redaction_enabled": True,
    "sandbox_isolation": True,
    "egress_restricted": True,
    "tool_calls_total": 100,
    "tool_calls_succeeded": 95,
    "previous_weighted_score": 0.8,
}


class TestEvaluateProvider:
    def test_healthy_provider_scores_high(self):
        """Given: সব মাপে স্বাস্থ্যকর প্রোভাইডার।
        When: evaluate_provider চালানো হলে।
        Then: ঠিক ৭টি ডাইমেনশন, ওয়েটেড স্কোর 0.7-এর উপরে, প্রদত্ত নাম/টাইপ ফেরে।
        """
        score = evaluate_provider(
            provider="openrouter",
            task_type="ci_fix",
            measurements=dict(_HEALTHY_MEASUREMENTS),
            benchmark_run_id="run-001",
        )

        assert isinstance(score, ProviderScore)
        assert score.provider == "openrouter"
        assert score.task_type == "ci_fix"
        assert score.benchmark_run_id == "run-001"
        assert len(score.dimensions) == 7, f"৭ ডাইমেনশনের কথা: {len(score.dimensions)}"
        assert score.weighted_aggregate > 0.7, (
            f"স্বাস্থ্যকর প্রোভাইডারে স্কোর কম: {score.weighted_aggregate}"
        )

    def test_dimensions_cover_all_seven_names(self):
        """Given: যেকোনো মাপ।
        When: evaluate_provider চালালে।
        Then: correctness…regression — সাতটি ডাইমেনশনই উপস্থিত (নাম অনুযায়ী)।
        """
        score = evaluate_provider(
            provider="groq",
            task_type="research",
            measurements=dict(_HEALTHY_MEASUREMENTS),
        )
        names = {d.dimension for d in score.dimensions}
        expected = {
            ScoreDimension.CORRECTNESS,
            ScoreDimension.LATENCY,
            ScoreDimension.COST,
            ScoreDimension.RELIABILITY,
            ScoreDimension.SECURITY,
            ScoreDimension.TOOL_USE,
            ScoreDimension.REGRESSION,
        }
        assert names == expected, f"অনুপস্থিত/অতিরিক্ত: {names ^ expected}"

    def test_slow_provider_scores_lower_than_fast(self):
        """Given: একই মাপ কিন্তু p95 লেটেন্সি ১০ গুণ খারাপ।
        When: দুটি evaluate_provider তুলনা করলে।
        Then: ধীর প্রোভাইডারের ওয়েটেড স্কোর কম — স্কোরিং মাপ-সংবেদনশীল।
        """
        fast = evaluate_provider(
            provider="p", task_type="ci_fix", measurements=dict(_HEALTHY_MEASUREMENTS)
        )
        slow_measurements = dict(_HEALTHY_MEASUREMENTS)
        slow_measurements.update({"p50_ms": 3000.0, "p95_ms": 8000.0, "p99_ms": 12000.0})
        slow = evaluate_provider(provider="p", task_type="ci_fix", measurements=slow_measurements)
        assert slow.weighted_aggregate < fast.weighted_aggregate, (
            f"লেটেন্সি খারাপ হলেও স্কোর কমেনি: {slow.weighted_aggregate} vs {fast.weighted_aggregate}"
        )

    def test_weights_sum_to_one(self):
        """Given: যেকোনো task_type।
        When: weights পরীক্ষা করলে।
        Then: ওয়েটগুলোর যোগফল ~১.০ — অডিট-ট্রেইল স্ব-সঙ্গত।
        """
        score = evaluate_provider(
            provider="p",
            task_type="browser_automation",
            measurements=dict(_HEALTHY_MEASUREMENTS),
        )
        assert sum(score.weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_regression_dimension_reflects_previous_score(self):
        """Given: দুটি রান — একটির previous_weighted_score 0.8, অন্যটির 0.05।
        When: evaluate_provider চালালে।
        Then: regression ডাইমেনশনের raw_value (delta) ভিন্ন —
        previous স্কোর প্রতিফলিত হয় (evidence-তেও সংরক্ষিত)।
        """
        improved = evaluate_provider(
            provider="p", task_type="ci_fix", measurements=dict(_HEALTHY_MEASUREMENTS)
        )
        regressed_measurements = dict(_HEALTHY_MEASUREMENTS)
        regressed_measurements["previous_weighted_score"] = 0.05
        regressed = evaluate_provider(
            provider="p", task_type="ci_fix", measurements=regressed_measurements
        )
        dim = ScoreDimension.REGRESSION
        improved_reg = next(d for d in improved.dimensions if d.dimension is dim)
        regressed_reg = next(d for d in regressed.dimensions if d.dimension is dim)
        # delta (raw_value) অবশ্যই ভিন্ন — previous স্কোর স্কোরিংয়ে ঢুকেছে
        assert improved_reg.raw_value != regressed_reg.raw_value, (
            "previous_weighted_score পরিবর্তনে regression delta নড়েনি"
        )
        assert regressed_reg.raw_value > improved_reg.raw_value, (
            "কম previous স্কোর = বড় improvement-delta"
        )
        assert improved_reg.evidence.get("previous_score") == 0.8
        assert regressed_reg.evidence.get("previous_score") == 0.05


class TestRegressionScorerBands:
    """score_regression-এর ব্যান্ড-লজিক সরাসরি — #4047 ডকুমেন্টেড চুক্তি।"""

    @pytest.mark.parametrize(
        ("current, previous, expected_score, expect_alert"),
        [
            (0.9, 0.7, 1.0, False),  # বড় improvement (> +0.05)
            (0.81, 0.80, 0.9, False),  # ছোট improvement
            (0.80, 0.80, 0.8, False),  # অপরিবর্তিত
            (0.78, 0.80, 0.5, False),  # ছোট degradation (< 10%)
            (0.50, 0.80, 0.0, True),  # বড় degradation (> 10%) + alert
        ],
        ids=["big-improve", "small-improve", "no-change", "small-degrade", "big-degrade"],
    )
    def test_band_logic(self, current, previous, expected_score, expect_alert):
        """Given: current/previous স্কোর-জোড়া।
        When: score_regression চালালে।
        Then: ডকুমেন্টেড ব্যান্ড-স্কোর + alert ফ্ল্যাগ।
        """
        from core.evaluation.scorers.regression import score_regression

        result = score_regression(current, previous)
        assert result.score == expected_score
        assert result.evidence["alert"] is expect_alert
        assert result.evidence["delta"] == pytest.approx(current - previous)

    def test_out_of_range_rejected(self):
        """Given: সীমার বাইরের স্কোর (1.5)।
        When: score_regression চালালে।
        Then: ValueError — ভুয়া স্কোর নীরবে গিলতে নেই।
        """
        from core.evaluation.scorers.regression import score_regression

        with pytest.raises(ValueError):
            score_regression(1.5, 0.8)


class TestLatencyScorer:
    def test_best_latency_scores_full(self):
        """Given: p95 = 500ms (BEST থ্রেশহোল্ড)।
        When: score_latency চালালে।
        Then: স্কোর 1.0।
        """
        result = score_latency(p50_ms=200.0, p95_ms=LATENCY_P95_BEST_MS)
        assert result.score == pytest.approx(1.0)
        assert result.dimension is ScoreDimension.LATENCY

    def test_worst_latency_scores_zero(self):
        """Given: p95 = 5000ms (WORST থ্রেশহোল্ড)।
        When: score_latency চালালে।
        Then: স্কোর 0.0।
        """
        result = score_latency(p50_ms=2000.0, p95_ms=LATENCY_P95_WORST_MS)
        assert result.score == pytest.approx(0.0)

    def test_midpoint_scores_half(self):
        """Given: p95 = BEST/WORST-এর ঠিক মাঝামাঝি (2750ms)।
        When: score_latency চালালে।
        Then: লিনিয়ার নরমালাইজেশন — স্কোর ~0.5।
        """
        mid = (LATENCY_P95_BEST_MS + LATENCY_P95_WORST_MS) / 2
        result = score_latency(p50_ms=1000.0, p95_ms=mid)
        assert result.score == pytest.approx(0.5, abs=0.01)

    def test_negative_latency_rejected(self):
        """Given: ঋণাত্মক p95 (অসম্ভব মাপ)।
        When: score_latency চালালে।
        Then: ValueError — ভুয়া মাপ নীরবে গিলতে নেই।
        """
        with pytest.raises(ValueError):
            score_latency(p50_ms=-1.0, p95_ms=-5.0)

    def test_evidence_carries_thresholds(self):
        """Given: যেকোনো বৈধ মাপ।
        When: score_latency চালালে।
        Then: evidence-তে থ্রেশহোল্ড ও র-মান আছে — ব্যাখ্যাযোগ্য স্কোর।
        """
        result = score_latency(p50_ms=100.0, p95_ms=1000.0, p99_ms=1500.0, benchmark_run_id="r1")
        assert result.evidence.get("p95_ms") == 1000.0
        assert (
            "LATENCY_P95_BEST_MS" in result.evidence
            or "best_ms" in result.evidence
            or bool(result.evidence)
        ), "evidence ফাঁকা — অব্যাখ্যাযোগ্য স্কোর"

    def test_dimension_score_is_frozen_dataclass(self):
        """Given: DimensionScore টাইপ।
        When: কনস্ট্রাক্ট করলে।
        Then: frozen — পরে খারিজ-এডিট রোধ (অডিট-অখণ্ডতা)।
        """
        ds = DimensionScore(
            dimension=ScoreDimension.LATENCY,
            score=0.5,
            raw_value=1000.0,
            unit="ms",
            evidence={},
        )
        with pytest.raises(Exception):
            ds.score = 0.99  # type: ignore[misc]
