"""Unit tests for ExtractiveSummarizer."""

from scout.extractor import ExtractiveSummarizer


def test_extractive_summary_generation():
    summarizer = ExtractiveSummarizer()
    article = (
        "SupremeAI is an autonomous cognitive AI operating system designed for zero infrastructure cost. "
        "It features dynamic self-evolution, persistent episodic memory, and multi-tenant security guardrails. "
        "The web scraping engine was previously limited to a single page fetcher without rate limits or deduplication. "
        "With the new policy-driven upgrade, it gains per-domain pacing, trust classifications, and link graph traversal. "
        "Furthermore, zero-token content reduction saves between thirty to fifty percent of downstream LLM spending. "
        "All components operate gracefully even when external AI providers are in an unconfigured state."
    )

    summary = summarizer.summarize(article, max_sentences=2, max_chars=300)
    assert len(summary) > 0
    assert len(summary) <= 300
    # Must contain key salient sentences
    assert "SupremeAI" in summary or "zero" in summary


def test_extractive_summary_short_text():
    summarizer = ExtractiveSummarizer()
    short = "Python is an interpreted high-level general-purpose programming language."
    summary = summarizer.summarize(short)
    assert summary == short
