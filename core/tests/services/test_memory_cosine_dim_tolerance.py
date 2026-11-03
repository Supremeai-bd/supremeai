"""
Dimension-tolerance tests for CascadeMemoryService._cosine_similarity (#2257).

Contract under test: the fallback Python ranking path must NEVER silently
corrupt scores on embedding-dimension mismatch (the old zip(strict=False)
implementation truncated the dot product while norms ran over full lengths —
wrong scores, no error, no log) and must make every mismatch OBSERVABLE.
"""

import math
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.memory_service import CascadeMemoryService  # noqa: E402


@pytest.fixture
def svc():
    # No DB connection needed — only the pure scoring helper is exercised.
    return CascadeMemoryService.__new__(CascadeMemoryService)


def test_equal_dims_exact_math(svc):
    a = [1.0, 0.0, 2.0]
    b = [2.0, 0.0, 1.0]
    expected = (1 * 2 + 0 + 2 * 1) / (math.sqrt(5) * math.sqrt(5))
    assert svc._cosine_similarity(a, b) == pytest.approx(expected)


def test_identical_vectors_score_one(svc):
    v = [0.5] * 8
    assert svc._cosine_similarity(v, list(v)) == pytest.approx(1.0)


def test_zero_vector_scores_zero(svc):
    assert svc._cosine_similarity([0.0, 0.0, 0.0], [1.0, 2.0, 3.0]) == 0.0


def test_dim_mismatch_scores_over_prefix_and_warns(svc):
    """384 query vs legacy 1536 stored row: score computed, warning emitted.

    core.logging_config routes through loguru, so we observe the module's
    logger directly (caplog cannot see it).
    """
    from services import memory_service as ms_mod

    query = [1.0, 0.0, 0.0]
    legacy = [1.0, 0.0, 0.0] + [0.0] * 1533  # 1536-dim legacy row shape
    with patch.object(ms_mod.logger, "warning") as warn:
        score = svc._cosine_similarity(query, legacy)
    assert score == pytest.approx(1.0)
    assert warn.called
    msg = " ".join(str(c.args[0]) for c in warn.call_args_list if c.args)
    assert "dimension mismatch" in msg


def test_dim_mismatch_prefix_semantics_correct(svc):
    """The prefix score must equal an explicit recompute, not the old
    dot-truncated/norms-full corruption."""
    a = [3.0, 4.0]  # 2-dim query
    b = [1.0, 0.0, 9.0, 9.0, 9.0]  # 5-dim legacy row
    # explicit prefix semantics: a[:2]=[3,4], b[:2]=[1,0]
    expected = (3 * 1 + 4 * 0) / (math.sqrt(25) * math.sqrt(1))
    assert svc._cosine_similarity(a, b) == pytest.approx(expected)


def test_dim_mismatch_old_code_would_corrupt(svc):
    """Regression proof: on orthogonal-tail rows the old implementation
    produced a different (corrupt) value than prefix semantics."""
    a = [1.0, 0.0]
    b = [1.0, 0.0, 5.0, 5.0, 5.0]
    correct = svc._cosine_similarity(a, b)
    # old code: dot over zip → 1*1 + 0*0 = 1; norms: |a|=1, |b|=sqrt(1+75)
    corrupt = 1.0 / (1.0 * math.sqrt(1.0 + 75.0))
    assert correct == pytest.approx(1.0)
    assert corrupt == pytest.approx(1.0 / math.sqrt(76))
    assert correct != pytest.approx(corrupt)


def test_empty_vectors_score_zero(svc):
    assert svc._cosine_similarity([], [1.0]) == 0.0
    assert svc._cosine_similarity([], []) == 0.0


def test_mismatch_warning_does_not_raise(svc):
    """Any dim combination must return a float — ranking must never crash."""
    for la, lb in ((1, 1536), (1536, 1), (0, 384), (384, 0)):
        out = svc._cosine_similarity([0.1] * la, [0.2] * lb)
        assert isinstance(out, float)
