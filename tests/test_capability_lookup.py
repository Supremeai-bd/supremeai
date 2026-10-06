"""Roadmap v2.0 Phase 8 regression guards (#4145) — Capability Before Construction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agents.capability_lookup import reuse_ladder, search


class CapabilityLookupTests(unittest.TestCase):
    def test_search_finds_real_inventory_entries(self):
        hits = search("redis")
        self.assertTrue(hits, "redis must hit the real inventories")
        self.assertTrue(any(h["source"] in ("capability_inventory.json", "inventory.yaml")
                            for h in hits))

    def test_unknown_query_lands_on_compose_or_new(self):
        r = reuse_ladder("quantum-flux-capacitor-driver")
        self.assertEqual(r["verdict"], "compose_or_new")
        self.assertIn("COMBINED", r["next"])

    def test_known_query_reuses(self):
        r = reuse_ladder("redis")
        self.assertEqual(r["verdict"], "reuse")
        self.assertTrue(r["existing"])

    def test_empty_query_is_safe(self):
        self.assertEqual(search(""), [])
        self.assertEqual(search("   "), [])

    def test_no_secret_values_surfaced(self):
        for h in search("redis", limit=20):
            blob = str(h).lower()
            for secret in ("ghs_", "sk_", "token=", "password"):
                self.assertNotIn(secret, blob)


if __name__ == "__main__":
    unittest.main()
