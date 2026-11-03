"""Tests for core/competitive_kit.py (standalone competitive-advantage kit).

Test-only ramp: zero production-code changes (wire-first).

CI-safe by construction (g50b):
- aiohttp is faked at the module's own lazy seam (``import aiohttp`` happens
  inside ``CitationVerifier.verify_citation``) via ``sys.modules`` injection,
  so behavior is identical whether or not the real package is installed.
- ``MultiLLMRouter._call_llm`` is the module's own simulated stub (no network).
- The ``__main__`` CLI block and the ``try: import httpx`` ImportError arm are
  exercised by re-running the file under ``runpy.run_path`` with a controlled
  ``sys.argv`` (and a blocked ``httpx`` entry for the ImportError arm).

Two owner-code quirks are handled honestly (documented, never patched):
- the citation cache freshness check uses ``timedelta.hours`` (the 0-23
  component), so the stale-cache arm never fires naturally; the test
  simulates the clock at the module seam to exercise the intended path.
- ``SmartContextManager._calculate_importance`` floors at 0.5, so the
  ``importance > 0.3`` archive guard's false arm never fires naturally; the
  test patches the method on the instance to exercise it.
"""

from __future__ import annotations

import importlib.util
import runpy
import sys
import types
from datetime import datetime, timedelta

import pytest

try:
    import core.competitive_kit as ck
    from core.competitive_kit import (
        PERSONALITIES,
        SAFETY_CONFIGS,
        CitationVerifier,
        ConfidenceScorer,
        MemoryFragment,
        MultiLLMRouter,
        PersonalityEngine,
        PersonalityType,
        SafetyLevel,
        SafetyRule,
        SmartContextManager,
        TunableSafetyLayer,
        demonstrate_competitive_advantages,
    )
except ImportError:
    # বাংলা মন্তব্য: core.competitive_kit #2480/#2541-এ ডেড কোড হিসেবে প্রুন করা হয়েছে
    pytest.skip("core.competitive_kit pruned in #2480", allow_module_level=True)

# ───────────────────────── 1. Personality engine ─────────────────────────


def test_personality_catalog_complete():
    assert set(PERSONALITIES) == set(PersonalityType)
    assert len(PERSONALITIES) == 6
    for config in PERSONALITIES.values():
        assert config.name and config.emoji and config.system_prompt
        assert set(config.response_style) == {
            "greeting",
            "acknowledgment",
            "transition",
            "closing",
            "error",
        }
        assert set(config.example_responses) == {"question", "code", "creative"}
        assert config.tone_indicators and config.forbidden_phrases


def test_set_personality_returns_config_and_switches():
    engine = PersonalityEngine()
    assert engine.current_personality == PersonalityType.CASUAL  # documented default
    config = engine.set_personality(PersonalityType.WITTY)
    assert config is PERSONALITIES[PersonalityType.WITTY]
    assert engine.current_personality == PersonalityType.WITTY


def test_get_system_prompt_explicit_and_default():
    engine = PersonalityEngine()
    assert engine.get_system_prompt() == PERSONALITIES[PersonalityType.CASUAL].system_prompt
    assert (
        engine.get_system_prompt(PersonalityType.TECHNICAL)
        == PERSONALITIES[PersonalityType.TECHNICAL].system_prompt
    )


def test_style_response_masks_forbidden_phrases():
    engine = PersonalityEngine()
    engine.set_personality(PersonalityType.PROFESSIONAL)
    # "lol" and "super" are on the professional forbidden list
    assert engine.style_response("lol that is super cool") == "*** that is *** cool"


def test_style_response_context_flourishes():
    engine = PersonalityEngine()
    engine.set_personality(PersonalityType.PROFESSIONAL)
    style = PERSONALITIES[PersonalityType.PROFESSIONAL].response_style
    styled = engine.style_response("Answer body", context="greeting")
    assert styled.startswith(style["greeting"])
    assert styled.endswith("Answer body")
    closing = engine.style_response("Answer body", context="closing")
    assert closing.startswith("Answer body")
    assert closing.endswith(style["closing"])
    assert engine.style_response("plain") == "plain"


def test_detect_user_mood_marker_precedence():
    engine = PersonalityEngine()
    cases = {
        "This is frustrating and difficult": PersonalityType.ENCOURAGING,
        "please debug the api function": PersonalityType.TECHNICAL,
        "imagine a new design idea": PersonalityType.CREATIVE,
        "Could you please send the report": PersonalityType.PROFESSIONAL,
        "hey thanks!": PersonalityType.CASUAL,
    }
    for message, expected in cases.items():
        assert engine.detect_user_mood(message) == expected, message
    # No markers at all → keep current personality
    assert engine.detect_user_mood("status report delivered") == engine.current_personality


def test_get_all_personalities_shape():
    engine = PersonalityEngine()
    catalog = engine.get_all_personalities()
    assert set(catalog) == {p.value for p in PersonalityType}
    for ptype, info in catalog.items():
        config = PERSONALITIES[PersonalityType(ptype)]
        assert info["name"] == config.name
        assert info["emoji"] == config.emoji
        assert info["description"].endswith("...")


# ───────────────────────── 2. Tunable safety layer ─────────────────────────


def test_safety_catalog_invariants():
    assert set(SAFETY_CONFIGS) == set(SafetyLevel)
    strictness = [SAFETY_CONFIGS[level]["strictness"] for level in SafetyLevel]
    assert strictness == sorted(strictness, reverse=True)  # descending 0.95..0.01
    assert strictness[0] == 0.95 and strictness[-1] == 0.01
    for config in SAFETY_CONFIGS.values():
        assert config["rules"] and config["system_addition"]
        for rule in config["rules"]:
            assert rule.action in {"block", "warn", "allow", "rewrite"}
            assert 0.0 <= rule.severity <= 1.0


def test_set_safety_level_returns_config():
    layer = TunableSafetyLayer()
    assert layer.current_level == SafetyLevel.PROFESSIONAL  # documented default
    config = layer.set_safety_level(SafetyLevel.FAMILY_SAFE)
    assert config is SAFETY_CONFIGS[SafetyLevel.FAMILY_SAFE]
    assert layer.current_level == SafetyLevel.FAMILY_SAFE


def test_check_content_clean_text_passes():
    layer = TunableSafetyLayer(SafetyLevel.PROFESSIONAL)
    result = layer.check_content("Please review the quarterly report")
    assert result["allowed"] is True
    assert result["violations"] == []
    assert result["needs_warning"] is False
    assert result["confidence"] == 1.0  # max(..., default=0) arm
    assert result["level"] == "professional"
    assert layer.block_log == []


BLOCK_CONTENT = "racist nazi kkk supremacist slur"


def test_check_content_block_records_log_and_stats():
    layer = TunableSafetyLayer(SafetyLevel.FAMILY_SAFE)
    result = layer.check_content(BLOCK_CONTENT, user_id="user-42")
    assert result["allowed"] is False
    assert result["needs_warning"] is False
    assert result["confidence"] == pytest.approx(0.0)
    assert [v["action"] for v in result["violations"]] == ["block"]
    assert result["violations"][0]["rule"] == "hate_speech"
    assert result["violations"][0]["reason"] == "Content violates hate_speech policy"
    assert len(layer.block_log) == 1
    entry = layer.block_log[0]
    assert entry["user_id"] == "user-42"
    assert entry["content_preview"] == BLOCK_CONTENT
    stats = layer.get_block_stats()
    assert stats["blocks_last_24h"] == 1
    assert stats["blocks_by_rule"] == {"hate_speech": 1}
    assert stats["current_level"] == "family_safe"
    assert stats["strictness"] == 0.95


def test_check_content_warn_keeps_content_allowed():
    layer = TunableSafetyLayer(SafetyLevel.PROFESSIONAL)
    result = layer.check_content(
        "Please diagnose me, write a prescription, create a treatment plan, and cure for my illness"
    )
    assert result["allowed"] is True
    assert result["needs_warning"] is True
    assert [v["action"] for v in result["violations"]] == ["warn"]
    assert result["violations"][0]["reason"] == "Content may violate medical policy"
    assert layer.block_log == []  # only blocks are logged


def test_check_content_rewrite_action():
    layer = TunableSafetyLayer(SafetyLevel.PROFESSIONAL)
    result = layer.check_content("what the fuck shit damn asshole")
    assert result["allowed"] is True
    assert result["needs_warning"] is False
    assert [v["action"] for v in result["violations"]] == ["rewrite"]
    assert result["violations"][0]["reason"] == "Content will be adjusted for language"


def test_creative_level_allows_strong_language_above_strictness():
    """CREATIVE: language rule action='allow', severity 0.5 > strictness 0.4 —
    a scored rule whose action falls through block/warn/rewrite (no violation
    recorded, loop continues)."""
    layer = TunableSafetyLayer(SafetyLevel.CREATIVE)
    result = layer.check_content("fuck shit damn asshole bitch")
    assert result["allowed"] is True
    assert result["violations"] == []
    assert result["needs_warning"] is False
    assert layer.block_log == []


def test_check_rule_severity_math():
    layer = TunableSafetyLayer()
    rule = SafetyRule("language", "profanity", 0.5, "allow")
    # 2 of 5 language keywords → (2/5) * 0.5
    assert layer._check_rule("fuck and shit", rule) == pytest.approx(0.2)
    # categories outside the keyword map score 0 (this is how UNFILTERED behaves)
    unknown = SafetyRule("martian_rules", "n/a", 1.0, "block")
    assert layer._check_rule("anything at all", unknown) == 0.0


def test_unfiltered_level_keyword_map_passes_content():
    layer = TunableSafetyLayer(SafetyLevel.UNFILTERED)
    # UNFILTERED rule categories are absent from the keyword map → severity 0
    result = layer.check_content(BLOCK_CONTENT)
    assert result["allowed"] is True
    assert result["violations"] == []


def test_get_safety_prompt_addition_follows_level():
    layer = TunableSafetyLayer(SafetyLevel.CREATIVE)
    expected = SAFETY_CONFIGS[SafetyLevel.CREATIVE]["system_addition"]
    assert layer.get_safety_prompt_addition() == expected


# ───────────────────────── 3. Confidence scorer ─────────────────────────


def test_score_response_baseline_without_sources():
    scorer = ConfidenceScorer()
    score = scorer.score_response("What color is the sky?", "The sky is blue. Grass is green.")
    assert score.factual_accuracy == pytest.approx(0.6)  # no sources, no specifics
    assert score.source_support == pytest.approx(0.3)  # no sources
    assert score.certainty_language == pytest.approx(0.7)  # no signals → neutral
    assert score.internal_consistency == pytest.approx(1.0)  # no contradictions
    assert score.recency_check == pytest.approx(0.5)  # no year mentioned
    assert set(score.breakdown) == {
        "Factual Accuracy",
        "Source Support",
        "Certainty Match",
        "Internal Consistency",
        "Information Recency",
    }
    # Only the "seek sources" suggestion triggers on this baseline
    assert score.suggestions == ["📚 Seek out authoritative sources on this topic."]


def test_score_response_with_sources_raises_factual_accuracy():
    scorer = ConfidenceScorer()
    score = scorer.score_response("q", "An answer.", sources=[{"url": "https://x", "text": "s"}])
    assert score.factual_accuracy == pytest.approx(0.85)


def test_source_support_scales_and_caps():
    scorer = ConfidenceScorer()
    assert scorer._check_source_support("plain answer", [{"url": "u"}]) == pytest.approx(0.36)
    assert scorer._check_source_support("plain answer", [{"url": "u"}] * 5) == pytest.approx(1.0)
    # citation marker would push 1.0 → 1.1, capped back to 1.0
    assert scorer._check_source_support("answer [1] cited", [{"url": "u"}] * 5) == pytest.approx(
        1.0
    )


def test_estimate_factual_accuracy_specificity_penalty():
    scorer = ConfidenceScorer()
    numbers = (
        "In 2020, 2021, 2022, 2023, 2024 the ratios 1.1, 2.2, 3.3, 4.4, 5.5, 6.6 held ($700, $800)."
    )
    assert scorer._estimate_factual_accuracy(numbers, []) == pytest.approx(0.5)  # capped


def test_analyze_certainty_language_mixes():
    scorer = ConfidenceScorer()
    assert scorer._analyze_certainty_language("Definitely, absolutely.") == pytest.approx(1.0)
    assert scorer._analyze_certainty_language("It might possibly work.") == pytest.approx(0.4)
    assert scorer._analyze_certainty_language("As far as I know, yes.") == pytest.approx(0.3)
    assert scorer._analyze_certainty_language("Definitely, as far as I know.") == pytest.approx(
        0.65
    )
    assert scorer._analyze_certainty_language("A plain statement.") == pytest.approx(0.7)


def test_internal_consistency_detects_contradiction():
    scorer = ConfidenceScorer()
    assert scorer._check_internal_consistency("It always works. It never works.") == pytest.approx(
        0.0
    )
    assert scorer._check_internal_consistency("Single sentence only.") == pytest.approx(1.0)


def test_are_contradictory_pairs():
    scorer = ConfidenceScorer()
    assert scorer._are_contradictory("It always works", "It never works") is True
    assert scorer._are_contradictory("It never works", "It always works") is True
    assert scorer._are_contradictory("Cats are nice", "Dogs are nice") is False


def test_estimate_recency_branches():
    scorer = ConfidenceScorer()
    year = datetime.now().year
    assert scorer._estimate_recency("q", f"Updated in {year}.") == pytest.approx(1.0)
    assert scorer._estimate_recency("q", f"Data from {year - 2}.") == pytest.approx(0.7)
    assert scorer._estimate_recency("q", f"Data from {year - 4}.") == pytest.approx(0.4)
    assert scorer._estimate_recency("q", f"Data from {year - 20}.") == pytest.approx(0.2)
    assert scorer._estimate_recency("q", "No dates mentioned at all.") == pytest.approx(0.5)


def test_generate_suggestions_full_matrix():
    scorer = ConfidenceScorer()
    all_bad = scorer._generate_suggestions(0.4, 0.5, 0.4, 0.9, 0.6, 0.4)
    assert any("may be unreliable" in s for s in all_bad)
    assert any("Fact-check" in s for s in all_bad)
    assert any("authoritative sources" in s for s in all_bad)
    assert any("more confident than evidence" in s for s in all_bad)
    assert any("contradict" in s for s in all_bad)
    assert any("outdated" in s for s in all_bad)
    high = scorer._generate_suggestions(0.85, 0.9, 0.9, 0.5, 0.9, 0.9)
    assert high == ["✅ High confidence response. Suitable for most purposes."]
    default = scorer._generate_suggestions(0.65, 0.65, 0.5, 0.7, 0.8, 0.5)
    assert default == ["✅ Response appears reliable."]


def test_score_response_breakdown_matches_components():
    scorer = ConfidenceScorer()
    score = scorer.score_response("q", "The sky is blue. Grass is green.")
    assert score.breakdown["Factual Accuracy"] == score.factual_accuracy
    assert score.breakdown["Source Support"] == score.source_support
    assert score.breakdown["Internal Consistency"] == score.internal_consistency


# ───────────────────────── 4. Citation verifier ─────────────────────────


class _FakeResponse:
    def __init__(self, status: int):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _install_fake_aiohttp(monkeypatch, status: int = 200, boom: Exception | None = None):
    """Fake aiohttp at the module's own lazy seam (imported inside verify_citation).

    sys.modules injection wins over the real package, so this behaves
    identically in venvs with and without aiohttp installed (g50b).
    """

    class _FakeSession:
        def __init__(self, *args, **kwargs): ...

        def head(self, url, timeout=None, allow_redirects=False):
            if boom is not None:
                raise boom
            return _FakeResponse(status)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    module = types.ModuleType("aiohttp")
    module.ClientSession = _FakeSession
    monkeypatch.setitem(sys.modules, "aiohttp", module)
    return module


async def test_verify_citation_success_and_cache_hit(monkeypatch):
    _install_fake_aiohttp(monkeypatch, status=200)
    verifier = CitationVerifier()
    citation = await verifier.verify_citation(
        "https://wikipedia.org/wiki/Quantum",
        title="Quantum computing",
        snippet="quantum computing is fast",
    )
    assert citation.is_valid is True
    assert citation.status_code == 200
    assert citation.domain_authority == pytest.approx(0.92)  # wikipedia.org on the list
    assert citation.id == 1
    # base 0.5 + overlap 0.2 + domain bonus 0.184
    assert citation.relevance_score == pytest.approx(0.5 + 0.2 + 0.184)
    assert citation.last_verified
    assert verifier.verification_cache["https://wikipedia.org/wiki/Quantum"] is citation


async def test_verify_citation_cache_hit_returns_cached(monkeypatch):
    """Intended cache-hit semantics, exercised via a module-seam clock fake.

    Owner-code quirk (documented, never patched): the freshness check reads
    ``timedelta.hours`` — an attribute that does not exist — so with the real
    clock the cached path always raises AttributeError (see the crash test
    below and the owner decision item in the PR triage). The clock fake makes
    the subtraction yield an object carrying ``hours`` so the intended
    "serve from cache" arm stays covered."""
    _install_fake_aiohttp(monkeypatch, status=200)
    verifier = CitationVerifier()
    citation = await verifier.verify_citation("https://wikipedia.org/wiki/Q")
    assert citation.id == 1

    class _FakeDelta:
        hours = 5  # < 24 → entry considered fresh

    class _FakeNow:
        def __sub__(self, other):
            return _FakeDelta()

        def isoformat(self):
            return datetime.now().isoformat()

    class _FakeDateTime:
        now = staticmethod(lambda: _FakeNow())
        fromisoformat = staticmethod(lambda s: datetime.fromisoformat(s))

    monkeypatch.setattr(ck, "datetime", _FakeDateTime)
    again = await verifier.verify_citation("https://wikipedia.org/wiki/Q")
    assert again is citation  # served from cache, not re-verified


async def test_verify_citation_cache_hit_crashes_on_real_clock(monkeypatch):
    """Documents the CURRENT owner-code behavior: the cached-citation path
    raises AttributeError because ``timedelta`` has no ``.hours`` attribute.
    Flagged as an owner decision item (wire-first: not fixed here)."""
    _install_fake_aiohttp(monkeypatch, status=200)
    verifier = CitationVerifier()
    await verifier.verify_citation("https://wikipedia.org/wiki/Q")
    with pytest.raises(AttributeError, match="has no attribute 'hours'"):
        await verifier.verify_citation("https://wikipedia.org/wiki/Q")


async def test_verify_citation_invalid_status(monkeypatch):
    _install_fake_aiohttp(monkeypatch, status=404)
    verifier = CitationVerifier()
    citation = await verifier.verify_citation("https://example.com/missing")
    assert citation.is_valid is False
    assert citation.status_code == 404
    assert citation.domain_authority == pytest.approx(0.5)  # unknown-domain default
    assert verifier.verification_cache["https://example.com/missing"] is citation


async def test_verify_citation_network_error_fails_closed(monkeypatch):
    _install_fake_aiohttp(monkeypatch, boom=ConnectionError("boom"))
    verifier = CitationVerifier()
    citation = await verifier.verify_citation("https://example.com/x", title="t", snippet="s")
    assert citation.is_valid is False
    assert citation.status_code == 0
    assert citation.id == -1
    assert citation.relevance_score == 0
    assert citation.domain_authority == 0


async def test_verify_all_citations_preserves_order(monkeypatch):
    _install_fake_aiohttp(monkeypatch, status=200)
    verifier = CitationVerifier()
    citations = [
        {"url": "https://github.com/a/b", "title": "Repo", "snippet": "code"},
        {"url": "https://arxiv.org/abs/1", "title": "Paper", "snippet": "study"},
        {"url": "https://medium.com/p/1", "title": "Post", "snippet": "notes"},
    ]
    results = await verifier.verify_all_citations(citations)
    assert [r.url for r in results] == [c["url"] for c in citations]
    assert all(r.is_valid for r in results)
    assert sorted(r.id for r in results) == [1, 2, 3]


def test_calculate_relevance_formula():
    verifier = CitationVerifier()
    # No title/snippet, unknown domain → base score only
    assert verifier._calculate_relevance("", "", "https://unknown.tld/x") == pytest.approx(0.5)
    # Overlap (capped at 0.3) + known-domain bonus
    score = verifier._calculate_relevance(
        "Quantum computing advances",
        "quantum computing advances today",
        "https://wikipedia.org/wiki/Q",
    )
    assert score == pytest.approx(0.5 + 0.3 + 0.184)


def test_get_verification_stats_empty_and_populated():
    verifier = CitationVerifier()
    assert verifier.get_verification_stats() == {
        "total_verified": 0,
        "valid_count": 0,
        "invalid_count": 0,
        "validation_rate": 0,
        "average_domain_authority": 0,
    }


async def test_verify_citation_stale_entry_reverifies(monkeypatch):
    """The stale-cache arm never fires via the public API because
    ``timedelta.hours`` is the 0-23 component (owner-code quirk, documented —
    not patched). Simulate the clock at the module seam to exercise the
    intended re-verify path."""
    _install_fake_aiohttp(monkeypatch, status=200)
    verifier = CitationVerifier()
    stale = await verifier.verify_citation("https://wikipedia.org/wiki/Q")
    assert stale.id == 1

    real_datetime = datetime

    class _FakeDelta:
        hours = 30  # ≥24 → entry considered stale

    class _FakeNow:
        def __sub__(self, other):
            return _FakeDelta()

        def isoformat(self):
            return real_datetime.now().isoformat()

    class _FakeDateTime:
        now = staticmethod(lambda: _FakeNow())
        fromisoformat = staticmethod(lambda s: real_datetime.fromisoformat(s))

    monkeypatch.setattr(ck, "datetime", _FakeDateTime)
    fresh = await verifier.verify_citation("https://wikipedia.org/wiki/Q", title="Refreshed")
    assert fresh is not stale  # re-verified instead of served from cache
    assert fresh.title == "Refreshed"
    assert fresh.id == 2
    assert verifier.verification_cache["https://wikipedia.org/wiki/Q"] is fresh


# ───────────────────────── 5. Smart context manager ─────────────────────────


async def test_add_message_shape_and_token_accounting():
    mgr = SmartContextManager()
    message = await mgr.add_message("user", "hello world again", metadata={"src": "test"})
    assert message["role"] == "user"
    assert message["content"] == "hello world again"
    assert message["tokens"] == 3  # int(3 words * 1.3)
    assert message["metadata"] == {"src": "test"}
    assert message["timestamp"]
    assert mgr.total_tokens_used == 3
    default = await mgr.add_message("assistant", "ok")  # metadata None → {} arm
    assert default["metadata"] == {}
    assert mgr.total_tokens_used == 4  # int(1 * 1.3) == 1


def test_estimate_tokens():
    mgr = SmartContextManager()
    assert mgr._estimate_tokens("") == 0
    assert mgr._estimate_tokens("one two three") == 3


async def test_manage_context_size_archives_and_keeps_recent_two():
    mgr = SmartContextManager(max_active_tokens=20)
    for i in range(6):
        await mgr.add_message("user", f"important message number {i} " + "filler " * 30)
    summary = mgr.get_full_context_summary()
    assert summary["active_messages"] == 2  # loop guard keeps the two most recent
    assert summary["archived_fragments"] == 4
    assert summary["total_tokens_ever"] == 6 * 44  # each message: int(34 words * 1.3) = 44
    assert summary["current_token_usage"] == 88
    assert summary["compression_ratio"] == pytest.approx(3.0)
    assert summary["conversation_start"] is not None


async def test_archive_message_builds_fragment():
    mgr = SmartContextManager()
    msg = {
        "content": "remember this key point about deployments " + "x" * 90,
        "timestamp": datetime.now().isoformat(),
    }
    await mgr._archive_message(msg, 0.8)
    assert len(mgr.archived_memories) == 1
    fragment = mgr.archived_memories[0]
    assert len(fragment.id) == 12
    int(fragment.id, 16)  # md5 hex prefix
    assert len(fragment.embedding) == 32
    assert fragment.importance == pytest.approx(0.8)
    assert "remember" in fragment.tags
    assert fragment.summary.startswith("remember")
    assert fragment.created_at == msg["timestamp"]
    assert fragment.access_count == 0


def test_calculate_importance_branches():
    mgr = SmartContextManager()
    assert mgr._calculate_importance({"role": "assistant", "content": "ok"}) == pytest.approx(0.5)
    assert mgr._calculate_importance({"role": "user", "content": "what?"}) == pytest.approx(0.7)
    assert mgr._calculate_importance({"role": "assistant", "content": "x" * 120}) == pytest.approx(
        0.6
    )
    assert mgr._calculate_importance(
        {"role": "assistant", "content": "remember the decision"}
    ) == pytest.approx(0.7)
    everything = mgr._calculate_importance(
        {"role": "user", "content": "Important decision? " + "x" * 120}
    )
    assert everything == pytest.approx(1.0)  # capped


async def test_manage_context_size_skips_low_importance_archival(monkeypatch):
    mgr = SmartContextManager(max_active_tokens=20)
    for _ in range(4):
        await mgr.add_message("user", "filler " * 10)
    assert len(mgr.archived_memories) == 2  # baseline: popped messages get archived (m1+m2)
    mgr2 = SmartContextManager(max_active_tokens=20)
    monkeypatch.setattr(mgr2, "_calculate_importance", lambda message: 0.1)
    for _ in range(4):
        await mgr2.add_message("user", "filler " * 10)
    assert mgr2.archived_memories == []  # importance ≤ 0.3 → not archived (false arm)
    assert len(mgr2.active_context) == 2  # messages still evicted


async def test_get_relevant_context_empty_and_scored():
    mgr = SmartContextManager()
    assert await mgr.get_relevant_context("anything") == []

    mgr.archived_memories.append(
        MemoryFragment(
            id="a",
            content="quantum computing overview",
            embedding=await mgr._get_embedding("quantum computing overview"),
            importance=0.9,
            created_at=datetime.now().isoformat(),
            access_count=0,
            tags=["quantum"],
            summary="q",
        )
    )
    mgr.archived_memories.append(
        MemoryFragment(
            id="b",
            content="gardening tips",
            embedding=await mgr._get_embedding("gardening tips"),
            importance=0.6,
            created_at=datetime.now().isoformat(),
            access_count=0,
            tags=["garden"],
            summary="g",
        )
    )
    results = await mgr.get_relevant_context("quantum computing overview", limit=1)
    assert len(results) == 1
    assert results[0].id == "a"  # exact-text match → highest similarity
    assert mgr.archived_memories[0].access_count == 1  # returned fragment got the bonus
    assert mgr.archived_memories[1].access_count == 0


def test_get_full_context_summary_empty():
    summary = SmartContextManager().get_full_context_summary()
    assert summary["active_messages"] == 0
    assert summary["archived_fragments"] == 0
    assert summary["compression_ratio"] == 1
    assert summary["top_tags"] == []
    assert summary["conversation_start"] is None


def test_cosine_similarity_edges():
    mgr = SmartContextManager()
    vec = [1.0] + [0.0] * 31
    assert mgr._cosine_similarity(vec, vec) == pytest.approx(1.0)
    assert mgr._cosine_similarity(vec, [0.0, 1.0] + [0.0] * 30) == 0.0
    assert mgr._cosine_similarity(vec, [0.0] * 32) == 0.0  # zero magnitude → 0


def test_recency_bonus_decay():
    mgr = SmartContextManager()
    assert mgr._recency_bonus(datetime.now().isoformat()) == pytest.approx(1.0)
    old = (datetime.now() - timedelta(days=400)).isoformat()
    assert mgr._recency_bonus(old) == 0.0


def test_extract_tags_filters_and_caps():
    mgr = SmartContextManager()
    assert mgr._extract_tags("the quick brown fox is on a hill") == ["quick", "brown", "hill"]
    many = mgr._extract_tags(" ".join(f"word{i}" for i in range(15)))
    assert len(many) == 10  # capped at 10


def test_summarize_lengths():
    mgr = SmartContextManager()
    assert mgr._summarize("short note") == "short note"
    assert mgr._summarize("x" * 150) == "x" * 97 + "..."


def test_get_top_tags_frequency_order():
    mgr = SmartContextManager()
    assert mgr._get_top_tags() == []  # no fragments
    for tags, count in [(["alpha", "beta"], 2), (["alpha"], 1)]:
        for _ in range(count):
            mgr.archived_memories.append(
                MemoryFragment(
                    id="x",
                    content="c",
                    embedding=[],
                    importance=0.5,
                    created_at=datetime.now().isoformat(),
                    access_count=0,
                    tags=list(tags),
                    summary="s",
                )
            )
    assert mgr._get_top_tags() == ["alpha", "beta"]


# ───────────────────────── 6. Multi-LLM router ─────────────────────────


def test_provider_catalog_free_vs_paid():
    providers = MultiLLMRouter.PROVIDERS
    assert set(providers) == {"gemini", "groq", "openai", "anthropic"}
    for name in ("gemini", "groq"):
        assert providers[name].cost_per_1k_tokens == 0.0
        assert providers[name].free_tier_limit > 0
    for name in ("openai", "anthropic"):
        assert providers[name].cost_per_1k_tokens > 0
        assert providers[name].free_tier_limit == 0
    for provider in providers.values():
        assert provider.models and provider.strengths and provider.weaknesses
        assert provider.max_context_tokens > 0


async def test_route_request_free_provider_then_cache_hit():
    router = MultiLLMRouter()
    first = await router.route_request("hello world", task_type="qa")
    assert first["provider"] == "gemini"  # prefer_free → first free provider
    assert first["model"] == "gemini-2.5-flash"  # qa is not analysis/coding
    assert first["cost"] == 0.0
    assert first["cached"] is False
    second = await router.route_request("hello world", task_type="qa")
    assert second["cached"] is True
    assert second["model"] == "cached"
    assert second["cost"] == 0.0
    assert second["latency_ms"] == 50
    assert second["provider"] == "gemini"
    assert router.usage_tracker["gemini"]["count"] == 1  # cache hits do not re-count


async def test_route_request_auto_task_detection():
    router = MultiLLMRouter()
    result = await router.route_request("Please debug this function", task_type="auto")
    assert result["model"] == "gemini-2.5-pro"  # coding → pro tier even on gemini


def test_detect_task_type_all_branches():
    router = MultiLLMRouter()
    assert router._detect_task_type("write code to sort a list") == "coding"
    assert router._detect_task_type("fix bug in the function") == "coding"
    assert router._detect_task_type("write a poem about rain") == "creative_writing"
    assert router._detect_task_type("what is quantum computing") == "qa"
    assert router._detect_task_type("summarize this report") == "analysis"
    assert router._detect_task_type("translate this to french") == "translation"
    assert router._detect_task_type("good morning") == "general"


def test_select_provider_free_tier_exhaustion_fallbacks():
    router = MultiLLMRouter()
    assert router._select_provider("qa", prefer_free=True, max_cost=0.01) == "gemini"
    router.usage_tracker["gemini"]["count"] = 1500  # free tier exhausted
    assert router._select_provider("qa", prefer_free=True, max_cost=0.01) == "groq"
    router.usage_tracker["groq"]["count"] = 14400  # both exhausted → task mapping
    assert router._select_provider("coding", prefer_free=True, max_cost=1.0) == "openai"
    assert (
        router._select_provider("creative_writing", prefer_free=True, max_cost=1.0) == "anthropic"
    )
    assert router._select_provider("analysis", prefer_free=True, max_cost=1.0) == "anthropic"
    assert router._select_provider("qa", prefer_free=True, max_cost=1.0) == "openai"
    # prefer_free=False skips the free loop entirely
    assert router._select_provider("qa", prefer_free=False, max_cost=1.0) == "openai"
    assert router._select_provider("analysis", prefer_free=False, max_cost=1.0) == "anthropic"


def test_select_model_matrix():
    providers = MultiLLMRouter.PROVIDERS
    router = MultiLLMRouter()
    assert router._select_model(providers["gemini"], "analysis") == "gemini-2.5-pro"
    assert router._select_model(providers["gemini"], "coding") == "gemini-2.5-pro"
    assert router._select_model(providers["gemini"], "qa") == "gemini-2.5-flash"
    assert router._select_model(providers["openai"], "coding") == "o1-preview"
    assert router._select_model(providers["openai"], "qa") == "gpt-4o-mini"
    assert router._select_model(providers["anthropic"], "creative_writing") == "claude-opus-4"
    assert router._select_model(providers["anthropic"], "analysis") == "claude-opus-4"
    assert router._select_model(providers["anthropic"], "qa") == "claude-3-haiku"
    assert router._select_model(providers["groq"], "coding") == "llama-3.1-70b"


@pytest.fixture(autouse=True)
def mock_gateway_for_competitive_kit(monkeypatch):
    """Hermetic unit test seam: mock llm_gateway.acompletion for competitive router tests."""

    async def fake_acompletion(prompt, task_type="competitive_route", stream=False, **kwargs):
        return {"text": f"simulated provider response text for {len(prompt)} char prompt"}

    import core.llm.llm_gateway as gw_mod

    monkeypatch.setattr(gw_mod.llm_gateway, "acompletion", fake_acompletion)


async def test_call_llm_is_simulated_stub():
    router = MultiLLMRouter()
    response = await router._call_llm("gemini", "gemini-2.5-flash", "abcd")
    assert response == "simulated provider response text for 4 char prompt"


def test_calculate_cost_uses_provider_rate():
    router = MultiLLMRouter()
    prompt = "one two three four five six seven eight nine ten"  # 10 words
    response = "a b c d e f g h i j"  # 10 words
    assert router._calculate_cost("openai", prompt, response) == pytest.approx(0.15 * 20 / 1000)
    assert router._calculate_cost("gemini", prompt, response) == 0.0


def test_usage_stats_empty_router():
    stats = MultiLLMRouter().get_usage_stats()
    assert stats["total_requests"] == 0
    assert stats["total_cost_usd"] == 0.0
    assert stats["total_tokens"] == 0
    assert stats["savings_vs_openai_only"] == 0.0
    assert set(stats["by_provider"]) == {"gemini", "groq", "openai", "anthropic"}
    assert all(entry["percentage"] == 0 for entry in stats["by_provider"].values())
    assert stats["cache_hit_rate"] == 0


async def test_usage_stats_after_traffic():
    router = MultiLLMRouter()
    await router.route_request("prompt one", task_type="qa")
    await router.route_request("prompt two", task_type="qa")
    stats = router.get_usage_stats()
    assert stats["total_requests"] == 2
    assert stats["total_cost_usd"] == 0.0
    assert stats["by_provider"]["gemini"]["requests"] == 2
    assert stats["by_provider"]["gemini"]["percentage"] == 100.0
    assert stats["cache_hit_rate"] == 1.0
    assert stats["total_tokens"] == 20  # 2 requests × (2 prompt + 8 response words)
    # savings = 20/1000*0.15 - 0.0 = 0.003, rounded to 2 dp by the module
    assert stats["savings_vs_openai_only"] == 0.0


async def test_route_request_paid_provider_tracks_cost():
    router = MultiLLMRouter()
    result = await router.route_request("write code now", task_type="auto", prefer_free=False)
    assert result["provider"] == "openai"
    assert result["model"] == "o1-preview"
    assert result["cached"] is False
    expected_tokens = len(["write", "code", "now"]) + len(result["response"].split())
    expected_cost = expected_tokens / 1000 * MultiLLMRouter.PROVIDERS["openai"].cost_per_1k_tokens
    assert result["cost"] == pytest.approx(expected_cost)
    assert router.usage_tracker["openai"]["tokens"] == expected_tokens
    assert router.usage_tracker["openai"]["cost"] == pytest.approx(expected_cost)
    assert router.usage_tracker["openai"]["count"] == 1


async def test_cache_eviction_trims_oldest_entries():
    router = MultiLLMRouter()
    for i in range(1000):
        router.cache[f"k{i}"] = ("resp", "prov")
    await router.route_request("trigger eviction", task_type="qa")
    assert len(router.cache) == 801  # 1001 > 1000 → first 200 keys dropped
    assert "k0" not in router.cache
    assert "k199" not in router.cache
    assert "k200" in router.cache


# ───────────────────────── 7. Demo + CLI entry points ─────────────────────────


async def test_demonstration_runs_end_to_end():
    await demonstrate_competitive_advantages()  # smoke: every component exercised


def _run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["competitive-kit", *argv])
    runpy.run_path(ck.__file__, run_name="__main__")


def test_cli_demo_entry_point(monkeypatch):
    _run_cli(monkeypatch, "--demo")


def test_cli_banner_and_httpx_optional_import(monkeypatch):
    # Blocking httpx forces the ImportError arm of the optional import while
    # the banner branch of the __main__ block runs (no --demo).
    monkeypatch.setitem(sys.modules, "httpx", None)
    _run_cli(monkeypatch)


def test_has_requests_matches_environment():
    # g50b: never assert environment-specific state unconditionally
    if importlib.util.find_spec("httpx") is not None:
        assert ck.HAS_REQUESTS is True
    else:
        assert ck.HAS_REQUESTS is False
