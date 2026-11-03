"""ERR-H06 / ERR-G07 / ERR-G08 regression tests.

- ``agents.research_assistant`` must exist and really work (search via live
  arXiv is network-gated; summarize/citations are fully offline-deterministic).
- ``list_agents`` must reflect the real backend/agents/ catalog (no hardcoded
  single entry).
- ``get_agent_status`` must 404 unknown ids and never fabricate telemetry.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi import HTTPException

from agents.research_assistant import ResearchAssistant, ResearchSourceError
from api.routes import agents as agents_routes

# ----------------------------------------------------------------- summarize


def test_summarize_is_real_extractive_summarization() -> None:
    text = (
        "Transformers have revolutionized natural language processing. "
        "Attention mechanisms let models weigh every token against every other token. "
        "Training large transformers requires enormous compute budgets. "
        "Distillation can shrink models while preserving most of their quality. "
        "Future work explores sparse attention to reduce quadratic cost."
    )
    paper = {"title": "On Attention", "summary": text}
    out = ResearchAssistant().summarize(paper)
    assert out["method"] == "extractive-term-frequency"
    assert out["key_sentences"], "must keep at least one sentence"
    assert all(s in text for s in out["key_sentences"]), (
        "sentences must come from the input (no fabrication)"
    )
    assert out["keywords"], "must extract keywords"
    assert out["compression"]["original_sentences"] == 5


def test_summarize_rejects_empty_paper() -> None:
    with pytest.raises(ValueError):
        ResearchAssistant().summarize({})


# ----------------------------------------------------------------- citations


def test_citations_apa_ieee_bibtex_deterministic() -> None:
    paper = {
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "published": "2017-06-12T00:00:00Z",
        "url": "https://arxiv.org/abs/1706.03762",
        "venue": "arXiv",
    }
    ra = ResearchAssistant()
    apa = ra.citations(paper, style="apa")
    ieee = ra.citations(paper, style="ieee")
    bib = ra.citations(paper, style="bibtex")
    assert "2017" in apa and "Vaswani" in apa
    assert "Vaswani" in ieee and "Attention Is All You Need" in ieee and "2017" in ieee
    assert bib.startswith("@misc{vaswani2017")
    # deterministic
    assert apa == ra.citations(paper, style="apa")


def test_citations_unknown_style_rejected() -> None:
    with pytest.raises(ValueError):
        ResearchAssistant().citations({"title": "X"}, style="chicago-turabian-unknown")


# -------------------------------------------------------------------- search


def test_search_rejects_unsupported_source_instead_of_fabricating() -> None:
    with pytest.raises(ValueError, match="unsupported research source"):
        ResearchAssistant().search("attention", source="not-a-real-source")


def test_search_rejects_empty_query() -> None:
    with pytest.raises(ValueError):
        ResearchAssistant().search("   ")


@pytest.mark.requires_network
def test_search_hits_live_arxiv() -> None:
    """Live arXiv round trip (skipped in CI without network)."""
    try:
        results = ResearchAssistant().search("attention is all you need", max_results=2)
    except ResearchSourceError:
        pytest.skip("arXiv unreachable from this environment")
    assert isinstance(results, list)
    assert len(results) <= 2
    for paper in results:
        assert paper["title"]
        assert paper["source"] == "arxiv"


# ------------------------------------------------------------------- catalog


def test_list_agents_reflects_real_directory() -> None:
    catalog = agents_routes._agent_catalog()
    ids = {entry["id"] for entry in catalog}
    # real modules that actually exist in backend/agents/
    assert "churn_prophet" in ids
    assert "research_assistant" in ids
    # the old hardcoded lie is gone: research now maps to the real module
    entry = next(e for e in catalog if e["id"] == "research_assistant")
    assert entry["name"]


def test_get_agent_status_known_id_honest() -> None:
    import anyio

    result = anyio.run(agents_routes.get_agent_status, "research_assistant")
    assert result["status"] in {"available", "unavailable"}
    assert result["last_activity"] is None, "must not fabricate a timestamp"
    assert "telemetry" in result["detail"] or "import failed" in result["detail"]


def test_get_agent_status_unknown_id_honest() -> None:
    import anyio

    with pytest.raises(HTTPException) as excinfo:
        anyio.run(agents_routes.get_agent_status, "definitely-not-a-real-agent")
    assert excinfo.value.status_code == 404
