"""
backend/tests/test_advanced_wiring.py
=====================================
Verifies non-advanced -> advanced upgrades are correctly wired into the
advanced spine (model_router, adaptive_engine, semantic_cache, ErrorPatternDB, etc.).
"""

import pytest


@pytest.mark.asyncio
async def test_i18n_ai_translate_wiring():
    """Verify AI translation route works with graceful fallback."""
    from api.routes.localization import AITranslateRequest, ai_translate, get_bhasha_bot

    bot = get_bhasha_bot()
    payload = AITranslateRequest(key="welcome", target_lang="bn")
    res = await ai_translate(payload, bot=bot)
    assert "translation" in res
    assert res["translation"] is not None


@pytest.mark.asyncio
async def test_health_check_predictive_wiring():
    """Verify predictive health check functions without crash."""
    from core.health_check import health_checker

    res = await health_checker.check_all()
    assert "status" in res
    assert "predictions" in res
    assert "summary" in res


@pytest.mark.asyncio
async def test_email_drafting_wiring():
    """Verify email service AI drafting and optimal send hour."""
    from services.email.email_service import email_service

    draft = await email_service.draft("account_verification", {"email": "dev@supremeai.dev"})
    assert "subject" in draft
    assert "html_body" in draft
    hour = await email_service.optimal_send_hour("dev@supremeai.dev")
    assert 0 <= hour <= 24


@pytest.mark.asyncio
async def test_markdown_semantic_search_wiring():
    """Verify semantic markdown search endpoint."""
    from api.routes.markdown import semantic_search

    res = await semantic_search(q="orchestrator", top_k=3)
    assert "results" in res
    assert isinstance(res["results"], list)


@pytest.mark.asyncio
async def test_onboarding_plan_wiring():
    """Verify personalized onboarding plan generation."""
    from api.routes.onboarding import OnboardingPlanRequest, build_onboarding_plan

    req = OnboardingPlanRequest(locale="en", persona="developer")
    res = await build_onboarding_plan(req)
    assert "steps" in res
    assert len(res["steps"]) > 0
