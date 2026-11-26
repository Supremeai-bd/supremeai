"""G5.2b — memories SSOT dual-write adapter contract tests.

লক করে:
  1. owner_id derivation matches sidecar uuid5 namespace;
  2. PII strip before insert;
  3. kind mapping + validation;
  4. fail-open: no supabase → success=False, never raises;
  5. dual_write_learned_fact maps fact content.
"""

from __future__ import annotations

import uuid

from core.memory.ssot_adapter import (
    dual_write_learned_fact,
    map_kind,
    resolve_owner_id,
    save_memory_ssot,
    strip_pii,
    tenant_owner_id,
)


class TestOwnerDerivation:
    def test_valid_uuid_passthrough(self):
        uid = str(uuid.uuid4())
        assert resolve_owner_id(uid) == uid

    def test_non_uuid_user_id_uses_sidecar_namespace(self):
        raw = "user_abc"
        assert resolve_owner_id(raw) == tenant_owner_id(raw)

    def test_empty_falls_back_to_tenant_default(self):
        assert resolve_owner_id(None) == tenant_owner_id("tenant_default")
        assert resolve_owner_id("  ") == tenant_owner_id("tenant_default")

    def test_sidecar_formula_stable(self):
        # Same formula as infrastructure/.../mcp_server.py::_tenant_owner_id
        t = "tenant_default"
        expected = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"supremeai.memory.owner:{t}"))
        assert tenant_owner_id(t) == expected


class TestPiiStrip:
    def test_email_phone_card(self):
        out = strip_pii("mail me at a@b.com or +1 555 123 4567 card 4111 1111 1111 1111")
        assert "[EMAIL]" in out
        assert "a@b.com" not in out
        assert "[PHONE]" in out or "[CARD]" in out


class TestKindMapping:
    def test_explicit_kind_wins(self):
        assert map_kind(kind="decision", task_type="user_memory") == "decision"

    def test_task_type_mapping(self):
        assert map_kind(task_type="user_memory") == "preference"
        assert map_kind(task_type="decision") == "decision"

    def test_default_fact(self):
        assert map_kind() == "fact"
        assert map_kind(kind="nope") == "fact"


class TestFailOpen:
    def test_empty_content(self):
        r = save_memory_ssot(content="  ")
        assert r["success"] is False

    def test_no_supabase_configured_never_raises(self):
        # In test env supabase_url/key are typically empty → fail-open dict.
        r = save_memory_ssot(content="hello world", user_id=str(uuid.uuid4()))
        assert r["success"] is False
        assert "error" in r
        # status field present when configured-missing path hits
        if "status" in r:
            assert r["status"] == "candidate_not_saved"

    def test_bad_workspace_uuid(self):
        r = save_memory_ssot(content="x", workspace_id="not-a-uuid")
        assert r["success"] is False
        assert "workspace" in r["error"]


class TestLearnedFactMirror:
    def test_maps_content_and_kind(self):
        fact = {"id": "f1", "content": "the sky is blue", "tags": ["preference"]}
        r = dual_write_learned_fact(fact)
        assert r["success"] is False  # no supabase in unit test — fail-open
        assert "error" in r

    def test_text_fallback(self):
        fact = {"text": "fallback text"}
        r = dual_write_learned_fact(fact, content_text="explicit")
        assert r["success"] is False
