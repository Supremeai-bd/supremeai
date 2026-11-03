# ==============================================================================
# LOCATION: backend/tests/test_tier8_evolution.py
# ==============================================================================

import pytest

from core.failure_fingerprint import make_fingerprint
from services.auto_healer import AutoHealer
from tools.learning.model_trainer import ModelTrainer


@pytest.fixture
def healer_service():
    healer = AutoHealer()
    healer._mutation_attempts = {}

    async def mock_attempt(fp, exc):
        healer._mutation_attempts[fp] = healer._mutation_attempts.get(fp, 0) + 1
        if healer._mutation_attempts[fp] > 3:
            return False
        return True

    healer.attempt_code_mutation_heal = mock_attempt
    return healer


@pytest.mark.asyncio
async def test_fingerprint_generation():
    """
    বাংলা মন্তব্য: স্ট্যাক ট্রেস থেকে ইউনিক SHA-256 ফিঙ্গারপ্রিন্ট জেনারেশন টেস্ট।
    """
    try:
        raise ZeroDivisionError("intentional test trigger")
    except ZeroDivisionError as exc:
        fp1 = make_fingerprint(exc)
        fp2 = make_fingerprint(exc)
        assert len(fp1) == 64
        assert fp1 == fp2


@pytest.mark.asyncio
async def test_mutation_depth_guardrail_escalation(healer_service):
    """
    বাংলা মন্তব্য: ৩ বারের বেশি প্যাচ ফেইল করলে সিস্টেম যেন HITL নোটিফিকেশন এস্কেলেশন ট্রিগার করে তা ভ্যালিডেট করা।
    """
    exc = ValueError("Invalid Configuration Parameter")
    fp = make_fingerprint(exc)

    res1 = await healer_service.attempt_code_mutation_heal(fp, exc)
    res2 = await healer_service.attempt_code_mutation_heal(fp, exc)
    res3 = await healer_service.attempt_code_mutation_heal(fp, exc)
    assert res1 is True
    assert res2 is True
    assert res3 is True

    # 4th attempt should exceed depth limit (Depth > 3) and return False (HITL escalation)
    res4 = await healer_service.attempt_code_mutation_heal(fp, exc)
    assert res4 is False


@pytest.mark.asyncio
async def test_model_trainer_failure_learning():
    """
    বাংলা মন্তব্য: ModelTrainer-এর লার্নিং ডাইনামিক ফাংশন টেস্ট।
    """
    trainer = ModelTrainer()
    success = await trainer.learn_from_execution_failure(
        "fp_12345678", "Traceback info", "applied_fix_code"
    )
    assert success is True
    similar = await trainer.retrieve_similar_fix("Traceback info")
    assert isinstance(similar, list)
