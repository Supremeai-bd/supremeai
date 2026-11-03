"""CONTRACT BASELINE FREEZE — Wave 0.3 (issue #1226, WAVE_MASTER_PLAN §2).

বাংলা: এই suite চারটা পাবলিক কন্ট্রাক্টের **বর্তমান আচরণ** pin করে রাখে —
সিস্টেমের ভেতরে যা আছে সেটাই সত্য (Wave Master Plan §2, CP02 + CP06):

1. **CORS origin contract** — ``core.config_parsers.parse_origin_list``
   (canonical parser) + ``core.security.origin_validator._load_origins``
   (env → trusted-origins fail-closed contract, #1201-এ পুনরুদ্ধারকৃত)।
2. **JWT contract** — ``api.routes.auth`` token issuance + ``core.security``
   role-claim issuance + ``core.security.authentication.auth_middleware._decode_jwt``
   (HS256-only, verify_exp, refresh-as-access rejection, fail-closed secrets)।
3. **LLM router contract** — ``core.llm.llm_gateway.routing`` (policy load
   fail-safe, difficulty classification, call-chain assembly + dedupe +
   provider re-order, runtime override budget)।
4. **Frontend apiClient baseline** — ``frontend/src/services/apiClient.test.ts``
   (vitest) হলো apiClient-এর frozen baseline; নিচের ``TestFrontendBaselineRegistry``
   সেটার অস্তিত্ব ও runner binding guard করে।

**গেট নীতিমালা (Wave 0):** এই ফাইলের কোনো assert relax/বদল করা মানে এটা
CONTRACT CHANGE — আলাদা issue + justification ছাড়া নিষিদ্ধ। এই baseline-এর
উপর দাঁড়িয়ে Wave 1.1 (Zero-Bypass Inference Boundary CI gate) ও Wave 3-এর
collapse PRs (৩.২ gateway, ৩.৬ HTTP stack, ৩.৯ secret modules) নিরাপদে
refactor করা যাবে।
"""

from __future__ import annotations

import base64
import json
import time
from datetime import timedelta
from typing import Any

import pytest

import core.config
from core.config_parsers import parse_origin_list
from core.security.origin_validator import _load_origins

# ── 1. CORS origin contract ──────────────────────────────────────────────────


class TestCorsOriginContract:
    """parse_origin_list + _load_origins — canonical parsing + fail-closed."""

    def test_comma_list_is_stripped_and_empty_entries_dropped(self):
        assert parse_origin_list(" https://a.com , https://b.com ,,") == [
            "https://a.com",
            "https://b.com",
        ]

    def test_json_array_string_is_parsed(self):
        assert parse_origin_list('["https://a.com", "https://b.com"]') == [
            "https://a.com",
            "https://b.com",
        ]

    def test_existing_list_passes_through_canonicalized(self):
        assert parse_origin_list([" x ", "", "y"]) == ["x", "y"]

    def test_whitespace_only_string_yields_empty_list(self):
        assert parse_origin_list("   ") == []

    def test_non_string_non_list_returned_untouched(self):
        sentinel: dict[str, int] = {"k": 1}
        assert parse_origin_list(sentinel) is sentinel

    def test_env_empty_returns_default(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        default: frozenset[str] = frozenset({"https://keep.example"})
        assert _load_origins("CORS_ORIGINS", default) == default

    def test_env_comma_list_canonicalized(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", " https://a.com ,, https://b.com ")
        got = _load_origins("CORS_ORIGINS", frozenset())
        assert got == frozenset({"https://a.com", "https://b.com"})

    def test_env_json_list_canonicalized(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", '["https://a.com", " "]')
        got = _load_origins("CORS_ORIGINS", frozenset())
        assert got == frozenset({"https://a.com"})

    def test_env_json_non_list_fails_closed_to_default(self, monkeypatch):
        """#1201 security contract — dict-JSON কখনো trusted origin নয়।"""
        monkeypatch.setenv("CORS_ORIGINS", '{"not": "a list"}')
        default: frozenset[str] = frozenset({"https://default.example"})
        assert _load_origins("CORS_ORIGINS", default) == default

    def test_env_invalid_json_treated_as_comma_list(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://a.com,https://b.com")
        got = _load_origins("CORS_ORIGINS", frozenset())
        assert got == frozenset({"https://a.com", "https://b.com"})


# ── 2. JWT contract ──────────────────────────────────────────────────────────


def _segments(token: str) -> tuple[dict, dict, str]:
    header_b64, payload_b64, sig = token.split(".", 2)

    def _pad(part: str) -> str:
        return part + "=" * (-len(part) % 4)

    header = json.loads(base64.urlsafe_b64decode(_pad(header_b64)))
    payload = json.loads(base64.urlsafe_b64decode(_pad(payload_b64)))
    return header, payload, sig


class TestJwtContract:
    """Token issuance (api.routes.auth + core.security) + decode fail-closed."""

    # নোট (freeze সত্য): non-production-এ Settings প্রথম jwt_secret access-এ
    # একটা generated secret _jwt_secret_cache-এ বসিয়ে দেয় — issue/verify
    # সবসময় একই key দেখে। তাই wrong-key/fail-closed টেস্টগুলো singleton-এর
    # internals না ছুঁয়ে consumer boundary-তে patch করে (মডিউল রেফারেন্স /
    # forged token) — এটাই প্রোডাকশন আচরণের সঠিক pin।

    def test_access_token_shape_hs256_with_required_claims(self):
        from api.routes.auth import create_access_token
        from core.security.authentication import auth_middleware

        token = create_access_token({"sub": "user@example.com"})
        header, payload, _ = _segments(token)
        assert header["alg"] == "HS256"
        assert payload["type"] == "access"
        assert payload["sub"] == "user@example.com"
        assert payload["jti"]  # issued for revocation/audit trailing
        assert "exp" in payload and "iat" in payload
        decoded = auth_middleware._decode_jwt(token)
        assert decoded is not None and decoded["sub"] == "user@example.com"

    def test_access_token_preserves_caller_jti_and_honours_expiry_delta(self):
        from api.routes.auth import create_access_token

        _, payload, _ = _segments(create_access_token({"sub": "u@x.com", "jti": "fixed-jti"}))
        assert payload["jti"] == "fixed-jti"

        now = time.time()
        _, short, _ = _segments(
            create_access_token({"sub": "u@x.com"}, expires_delta=timedelta(minutes=5))
        )
        assert short["exp"] - now == pytest.approx(300, abs=5)

    def test_refresh_token_has_refresh_type_and_family_id(self):
        from api.routes.auth import create_refresh_token

        _, payload, _ = _segments(create_refresh_token({"sub": "u@x.com"}))
        assert payload["type"] == "refresh"
        assert payload["tfid"]  # token-family id for reuse detection
        _, with_family, _ = _segments(create_refresh_token({"sub": "u@x.com", "tfid": "family-1"}))
        assert with_family["tfid"] == "family-1"

    def test_refresh_token_rejected_as_access_token(self):
        """refresh-as-access ব্যবহার রোধ — _decode_jwt নিশ্চিতভাবে None।"""
        from api.routes.auth import create_refresh_token
        from core.security.authentication import auth_middleware

        assert auth_middleware._decode_jwt(create_refresh_token({"sub": "u@x.com"})) is None

    def test_tampered_signature_rejected(self):
        from api.routes.auth import create_access_token
        from core.security.authentication import auth_middleware

        token = create_access_token({"sub": "u@x.com"})
        tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
        assert auth_middleware._decode_jwt(tampered) is None

    def test_expired_token_rejected(self):
        from api.routes.auth import create_access_token
        from core.security.authentication import auth_middleware

        expired = create_access_token({"sub": "u@x.com"}, expires_delta=timedelta(seconds=-30))
        assert auth_middleware._decode_jwt(expired) is None

    def test_wrong_key_rejected(self):
        """অন্য key দিয়ে সই করা (forged) token — HS256 signature verify ফেল করে।"""
        import jwt as pyjwt

        from core.security.authentication import auth_middleware

        forged = pyjwt.encode(
            {"sub": "u@x.com", "type": "access", "exp": int(time.time()) + 300},
            "attacker-controlled-key",
            algorithm="HS256",
        )
        assert auth_middleware._decode_jwt(forged) is None

    def test_missing_secret_fails_closed(self, monkeypatch):
        """JWT secret না থাকলে decode কখনো সফল হয় না (fail-closed policy)।"""
        from types import SimpleNamespace

        from core.security.authentication import auth_middleware

        monkeypatch.setattr(auth_middleware, "settings", SimpleNamespace(jwt_secret=""))
        assert auth_middleware._decode_jwt("any.token.value") is None

    def test_core_security_token_derives_role_claim(self, monkeypatch):
        """core.security.create_access_token — admin_emails থেকে role claim।"""
        from core.security import create_access_token as core_create_token
        from core.security.authentication import auth_middleware

        monkeypatch.setattr(core.config.settings, "admin_emails", ["boss@example.com"])

        _, admin_payload, _ = _segments(core_create_token({"sub": "boss@example.com"}))
        assert admin_payload["role"] == "admin"
        _, user_payload, _ = _segments(core_create_token({"sub": "pleb@example.com"}))
        assert user_payload["role"] == "user"

        decoded = auth_middleware._decode_jwt(core_create_token({"sub": "boss@example.com"}))
        assert decoded is not None and decoded["role"] == "admin"


# ── 3. LLM router contract ───────────────────────────────────────────────────


def _make_router(policy: dict[str, Any]):
    """Minimal RoutingMixin subclass host — no gateway construction needed."""
    from core.llm.llm_gateway.routing import RoutingMixin

    class _Router(RoutingMixin):
        """Mixin host with a controlled routing_policy dict."""

    router = _Router()
    router.routing_policy = policy
    return router


class TestLlmRouterContract:
    """Routing policy load + call-chain assembly + runtime override budget."""

    POLICY: dict[str, Any] = {
        "complexity_rules": {
            "easy": ["openai/gpt-easy", "groq/g-easy"],
            "medium": ["openai/gpt-med"],
            "hard": ["openai/gpt-hard"],
        },
        "fallback_chain": ["gemini/gemini-2.5-flash", "bai/qwen3.8-flash"],
    }

    @pytest.fixture(autouse=True)
    def _task_map(self, monkeypatch):
        import core.llm.llm_gateway.routing as routing

        monkeypatch.setattr(routing, "TASK_MODEL_MAP", {"chat": "task/chat-model"})
        routing.clear_runtime_override()
        yield
        routing.clear_runtime_override()

    def _router(self):
        return _make_router(dict(self.POLICY))

    def test_policy_load_reads_real_file_with_canonical_keys(self):
        real = self._router()._load_routing_policy()
        assert isinstance(real, dict)
        assert {"complexity_rules", "fallback_chain"} <= set(real)

    def test_policy_load_missing_file_falls_back_safe(self, monkeypatch):
        import core.llm.llm_gateway.routing as routing

        monkeypatch.setattr(routing, "_POLICY_PATH", "/nonexistent/routing_policy.json")
        safe = self._router()._load_routing_policy()
        assert safe["complexity_rules"] == {}
        assert safe["fallback_chain"] == list(routing._DEFAULT_FALLBACK_MODELS)

    @pytest.mark.parametrize(
        ("task_type", "difficulty"),
        [
            ("code", "hard"),
            ("reasoning", "hard"),
            ("math", "hard"),
            ("agent", "medium"),
            ("analysis", "medium"),
            ("chat_summarize_style", "easy"),  # no TASK_MODEL_MAP entry → rules lead
        ],
    )
    def test_task_type_classifies_difficulty_and_leads_chain(self, task_type, difficulty):
        chain = self._router()._build_call_chain(None, None, task_type)
        assert chain[0] == self.POLICY["complexity_rules"][difficulty][0]

    def test_task_model_map_entry_leads_the_chain(self):
        """TASK_MODEL_MAP-এ entry থাকলে সেটাই chain হেড (complexity rules-এর আগে)।"""
        chain = self._router()._build_call_chain(None, None, "chat")
        assert chain[0] == "task/chat-model"
        assert chain[1] == self.POLICY["complexity_rules"]["easy"][0]

    def test_chain_assembly_order_dedupe_and_task_model(self):
        chain = self._router()._build_call_chain("explicit/model", None, "chat")
        # explicit model → task model → complexity_rules[easy] → fallbacks, no dups
        assert chain == [
            "explicit/model",
            "task/chat-model",
            "openai/gpt-easy",
            "groq/g-easy",
            "gemini/gemini-2.5-flash",
            "bai/qwen3.8-flash",
        ]

    def test_provider_reorder_puts_provider_models_first(self):
        chain = self._router()._build_call_chain(None, "groq", "chat")
        assert chain[0] == "groq/g-easy"
        rest = chain[1:]
        assert "openai/gpt-easy" in rest and "gemini/gemini-2.5-flash" in rest

    def test_runtime_override_prepends_and_budget_decrements(self):
        import core.llm.llm_gateway.routing as routing

        routing.set_runtime_override("override-prov", "override/model", remaining_requests=2)
        r = self._router()

        assert r._build_call_chain(None, None, "chat")[0] == "override/model"
        assert routing.get_runtime_override()["remaining_requests"] == 1
        assert r._build_call_chain(None, None, "chat")[0] == "override/model"
        # budget exhausted → override auto-clears
        state = routing.get_runtime_override()
        assert state["provider"] is None and state["model"] is None

    def test_explicit_model_beats_override_model(self):
        import core.llm.llm_gateway.routing as routing

        routing.set_runtime_override("prov", "override/model", remaining_requests=5)
        chain = self._router()._build_call_chain("explicit/model", None, "chat")
        assert chain[0] == "explicit/model"

    def test_empty_chain_falls_back_to_default_models(self, monkeypatch):
        import core.llm.llm_gateway.routing as routing

        monkeypatch.setattr(routing, "_DEFAULT_FALLBACK_MODELS", ["dflt/one", "dflt/two"])
        empty_router = _make_router({"complexity_rules": {}, "fallback_chain": []})
        # task_type-এর কোনো TASK_MODEL_MAP entry নেই এমন হতে হবে যেন chain খালি থাকে
        assert empty_router._build_call_chain(None, None, "summarize") == [
            "dflt/one",
            "dflt/two",
        ]


# ── 4. Frontend apiClient baseline registry ──────────────────────────────────


class TestFrontendBaselineRegistry:
    """apiClient-এর frozen baseline হলো vitest suite — এর অস্তিত্ব guard করি।

    রান: ``cd frontend && bun run test`` (vitest run) — CI-এর frontend job
    এটা চালায়; এই backend registry test নিশ্চিত করে ফাইলটা সরিয়ে ফেলা
    গেলে সেটা silent হবে না।
    """

    def test_apiclient_baseline_suite_exists(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        assert (root / "frontend" / "src" / "services" / "apiClient.ts").is_file()
        assert (root / "frontend" / "src" / "services" / "apiClient.test.ts").is_file()

    def test_vitest_is_the_frontend_test_runner(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        pkg = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))
        assert pkg["scripts"]["test"] == "vitest run"
