#!/usr/bin/env python3
"""Phase-1 memories SSOT tools (save_memory / recall_memories) — unit tests.

Stdlib-only; no network. Offline paths exercise validation + PII strip;
Supabase paths are stubbed via monkeypatch on module globals.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mcp_server as m  # noqa: E402


class TestSaveMemory(unittest.TestCase):
    def test_schema_has_both_tools(self):
        names = {t["name"] for t in m.TOOLS_SCHEMA}
        self.assertIn("save_memory", names)
        self.assertIn("recall_memories", names)

    def test_empty_content_rejected(self):
        self.assertEqual(m.handle_tool("save_memory", {"content": ""})["error"], "content is required")

    def test_invalid_kind_rejected(self):
        r = m.handle_tool("save_memory", {"content": "x", "kind": "nope"})
        self.assertIn("invalid kind", r["error"])

    def test_invalid_confidence_rejected(self):
        r = m.handle_tool("save_memory", {"content": "x", "confidence": 2})
        self.assertIn("confidence", r["error"])

    def test_invalid_owner_rejected(self):
        r = m.handle_tool("save_memory", {"content": "x", "owner_id": "not-a-uuid"})
        self.assertIn("owner_id", r["error"])

    def test_pii_strip_and_offline_fallback(self):
        r = m.handle_tool(
            "save_memory",
            {"content": "contact me at user@example.com or +8801712345678", "tenant_id": "tenant_default"},
        )
        self.assertEqual(r.get("status"), "candidate")
        self.assertEqual(r.get("source"), "offline_fallback")
        self.assertNotIn("user@example.com", r.get("content", ""))
        self.assertIn("[EMAIL]", r.get("content", ""))
        # deterministic owner derivation
        owner1 = m._tenant_owner_id("tenant_default")
        owner2 = m._tenant_owner_id("tenant_default")
        self.assertEqual(owner1, owner2)
        self.assertEqual(r.get("owner_id"), owner1)

    def test_supabase_insert_path(self):
        captured = {}

        def fake_request(table, method="GET", data=None, params=None):
            captured.update(table=table, method=method, data=data)
            return [{"id": "00000000-0000-0000-0000-000000000001", "status": "candidate"}]

        orig_url, orig_key = m.SUPABASE_URL, m.SUPABASE_KEY
        orig_fn = m._supabase_request
        m.SUPABASE_URL, m.SUPABASE_KEY = "https://example.supabase.co", "service-key"
        m._supabase_request = fake_request
        try:
            r = m.handle_tool("save_memory", {"content": "hello", "tenant_id": "t1"})
        finally:
            m.SUPABASE_URL, m.SUPABASE_KEY = orig_url, orig_key
            m._supabase_request = orig_fn
        self.assertEqual(captured["table"], "memories")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["data"]["status"], "candidate")
        self.assertEqual(captured["data"]["created_by"], "agent:t1")
        self.assertEqual(r["source"], "supabase")
        self.assertTrue(str(r["id"]))


class TestRecallMemories(unittest.TestCase):
    def test_query_required(self):
        self.assertEqual(m.handle_tool("recall_memories", {"query": ""})["error"], "query is required")

    def test_limit_clamped(self):
        captured = {}

        def fake_rpc(fn, payload):
            captured.update(fn=fn, payload=payload)
            return []

        orig_url, orig_key = m.SUPABASE_URL, m.SUPABASE_KEY
        orig_rpc = m._supabase_rpc
        m.SUPABASE_URL, m.SUPABASE_KEY = "https://example.supabase.co", "service-key"
        m._supabase_rpc = fake_rpc
        try:
            r = m.handle_tool("recall_memories", {"query": "hi", "limit": 999, "tenant_id": "t1"})
        finally:
            m.SUPABASE_URL, m.SUPABASE_KEY = orig_url, orig_key
            m._supabase_rpc = orig_rpc
        self.assertEqual(captured["fn"], "match_memories")
        self.assertEqual(captured["payload"]["match_count"], 50)
        self.assertEqual(captured["payload"]["query_text"], "hi")
        self.assertIsNone(captured["payload"]["query_embedding"])
        self.assertEqual(r["source"], "rpc:match_memories")

    def test_rpc_rows_get_owner_attached(self):
        def fake_rpc(fn, payload):
            return [{"id": "abc", "content": "x"}]

        orig_url, orig_key = m.SUPABASE_URL, m.SUPABASE_KEY
        orig_rpc = m._supabase_rpc
        m.SUPABASE_URL, m.SUPABASE_KEY = "https://example.supabase.co", "service-key"
        m._supabase_rpc = fake_rpc
        try:
            r = m.handle_tool("recall_memories", {"query": "x", "tenant_id": "tenant_a"})
        finally:
            m.SUPABASE_URL, m.SUPABASE_KEY = orig_url, orig_key
            m._supabase_rpc = orig_rpc
        self.assertEqual(r["memories"][0]["owner_id"], m._tenant_owner_id("tenant_a"))
        self.assertEqual(r["count"], 1)

    def test_offline_returns_error_shape(self):
        orig_url, orig_key = m.SUPABASE_URL, m.SUPABASE_KEY
        m.SUPABASE_URL, m.SUPABASE_KEY = "", ""
        try:
            r = m.handle_tool("recall_memories", {"query": "x"})
        finally:
            m.SUPABASE_URL, m.SUPABASE_KEY = orig_url, orig_key
        self.assertEqual(r["memories"], [])
        self.assertEqual(r["source"], "none")


if __name__ == "__main__":
    unittest.main(verbosity=2)
