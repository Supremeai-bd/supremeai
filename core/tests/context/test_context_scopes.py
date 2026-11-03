"""M2-B — scope chain tests (pure)."""

from __future__ import annotations

import pytest

from context.scopes import (
    SCOPE_ORDER,
    Scope,
    ScopeChainError,
    ScopeLevel,
    scope_distance,
    scope_match_score,
    validate_scope,
)


class TestScopeChain:
    def test_chain_order(self):
        assert SCOPE_ORDER == (
            ScopeLevel.GLOBAL,
            ScopeLevel.USER,
            ScopeLevel.WORKSPACE,
            ScopeLevel.PROJECT,
            ScopeLevel.CHAT,
            ScopeLevel.RUN,
            ScopeLevel.STEP,
        )

    def test_global_needs_nothing(self):
        validate_scope(Scope(level=ScopeLevel.GLOBAL))

    def test_user_level_requires_user_id(self):
        with pytest.raises(ScopeChainError, match="requires an id"):
            validate_scope(Scope(level=ScopeLevel.USER, user_id=None))
        validate_scope(Scope(level=ScopeLevel.USER, user_id="u1"))

    def test_run_level_requires_full_ancestry(self):
        # RUN requires user + chat + run; workspace/project optional (levels
        # between user and chat are required only up to the requested level's
        # parent in the CHAT branch — chain semantics: every level at or
        # below the requested one must carry identity).
        with pytest.raises(ScopeChainError, match="requires an id"):
            validate_scope(Scope(level=ScopeLevel.RUN, user_id="u1", run_id="r1"))  # chat missing

    def test_narrower_ids_than_request_rejected(self):
        with pytest.raises(ScopeChainError, match="narrower than"):
            validate_scope(Scope(level=ScopeLevel.USER, user_id="u1", run_id="r1"))

    def test_full_step_scope_valid(self):
        validate_scope(
            Scope(
                level=ScopeLevel.STEP,
                user_id="u1",
                chat_id="c1",
                run_id="r1",
                step_id="s1",
            )
        )

    def test_distance(self):
        assert scope_distance(ScopeLevel.USER, ScopeLevel.USER) == 0
        assert scope_distance(ScopeLevel.GLOBAL, ScopeLevel.STEP) == 6
        assert scope_distance(ScopeLevel.CHAT, ScopeLevel.RUN) == 1

    def test_scope_match_exact_is_one(self):
        assert scope_match_score(ScopeLevel.RUN, ScopeLevel.RUN) == 1.0

    def test_scope_match_decays(self):
        exact = scope_match_score(ScopeLevel.CHAT, ScopeLevel.CHAT)
        near = scope_match_score(ScopeLevel.RUN, ScopeLevel.CHAT)
        far = scope_match_score(ScopeLevel.GLOBAL, ScopeLevel.STEP)
        assert exact > near > far >= 0.0
