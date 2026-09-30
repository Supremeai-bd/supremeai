"""Scoped credential manager tests (Issue #2644 items 1, 2, 3, 7, 8).

Covers:
  * SSOT integrity — BOT_SLOT_CREDENTIALS invariants + push_as_agent import
  * Task-based scope filter — build_scoped_env allowlists / forbidden keys /
    rules_breaker zero-key sandbox
  * JIT installation-token mint — offline via injected fake transport+jwt
  * Ephemeral coder lease — TTL bounds, expiry housekeeping, active view
  * Zero-knowledge audit — presence-only, values never surfaced
  * continuous_agent_loop scoped spawn wiring — master keys withheld

No network access: every vault/mint call runs against injected fakes.
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agents import credential_manager as cm  # noqa: E402
from scripts.agents.credential_manager import (  # noqa: E402
    BOT_SLOT_CREDENTIALS,
)

# ───────────────────────────── fakes ─────────────────────────────

class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeTransport:
    """Dict-backed requests substitute: vault login + secrets + token mint."""

    def __init__(self, secrets: dict, token: str = "ghs_faketoken1234567890"):
        self.secrets = secrets
        self.token = token
        self.calls: list = []

    def post(self, url, data=None, headers=None, timeout=None, **kw):
        self.calls.append(("POST", url))
        if "universal-auth" in url:
            return FakeResponse({"accessToken": "at-xxx"})
        if "/access_tokens" in url:
            return FakeResponse({"token": self.token, "expires_in": 3600})
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url, params=None, headers=None, timeout=None, **kw):
        self.calls.append(("GET", url))
        if "secrets/raw" in url:
            return FakeResponse({
                "secrets": [
                    {"secretKey": k, "secretValue": v} for k, v in self.secrets.items()
                ]
            })
        raise AssertionError(f"unexpected GET {url}")


def fake_jwt_module():
    """Minimal stand-in for PyJWT.encode (offline mint tests)."""

    class FakeJwt:
        @staticmethod
        def encode(payload, key, algorithm=None):
            return json.dumps({"alg": algorithm, "iss": payload["iss"]}, sort_keys=True)

    return FakeJwt


# ───────────────────── SSOT integrity ─────────────────────

class BotSlotCredentialsTests(unittest.TestCase):
    def test_ssot_covers_all_documented_slots(self):
        for slot in ("agent-1", "agent-2", "agent-3", "agent-5", "agent-6"):
            self.assertIn(slot, cm.BOT_SLOT_CREDENTIALS, slot)

    def test_every_entry_has_required_fields(self):
        for slot, cfg in cm.BOT_SLOT_CREDENTIALS.items():
            for field in ("bot_name", "env_prefix", "role", "scopes"):
                self.assertIn(field, cfg, f"{slot}.{field}")
            self.assertTrue(cfg["bot_name"].startswith("supremeai-"), slot)

    def test_audit_pool_is_lease_only_with_issue_scopes(self):
        pool = cm.BOT_SLOT_CREDENTIALS["audit-pool"]
        self.assertTrue(pool.get("lease_only"))
        self.assertEqual(pool["scopes"], ["issues:write"])  # audit = issue-output only

    def test_push_as_agent_imports_ssot_not_inline(self):
        import scripts.git.push_as_agent as paa

        self.assertIs(paa.BOT_SLOT_CREDENTIALS, cm.BOT_SLOT_CREDENTIALS)
        source = Path(paa.__file__).read_text(encoding="utf-8")
        self.assertNotIn("BOT_SLOT_CREDENTIALS = {", source)

    def test_slot_config_unknown_slot_raises(self):
        with self.assertRaises(cm.CredentialError):
            cm.slot_config("agent-999")


# ───────────────────── task-based scope filter ─────────────────────

class ScopedEnvTests(unittest.TestCase):
    def test_coder_env_contains_only_allowlisted_keys(self):
        env = cm.build_scoped_env("coder", token="tok", agent_name="coder-1",
                                  slot="agent-3")
        self.assertIn("GH_TOKEN", env)
        self.assertEqual(env["AGENT_ROLE"], "coder")
        self.assertEqual(env["AGENT_SLOT"], "agent-3")
        self.assertEqual(env["AGENT_NAME"], "coder-1")
        self.assertEqual(env["GH_REPO"], "SaifulHaqueNiloy/supremeai")
        self.assertTrue(set(env) <= cm.TASK_SCOPED_ENV_KEYS["coder"] | {"GH_REPO", "AGENT_SLOT"})

    def test_forbidden_keys_never_pass_through_base_env(self):
        base = {
            "GH_TOKEN": "tok",
            "INFISICAL_CLIENT_SECRET": "master-secret",
            "GITHUB_APP_PRIVATE_KEY": "-----BEGIN...",
            "AGENT_NAME": "coder-1",
        }
        env = cm.build_scoped_env("coder", token="tok", base_env=base)
        self.assertNotIn("INFISICAL_CLIENT_SECRET", env)
        self.assertNotIn("GITHUB_APP_PRIVATE_KEY", env)
        self.assertEqual(env["AGENT_NAME"], "coder-1")

    def test_rules_breaker_gets_zero_keys(self):
        # #2644 §4: Rules Breaker = zero-key sandbox (negative testing)
        env = cm.build_scoped_env("rules_breaker", token="should-not-appear")
        self.assertEqual(env, {"GH_REPO": "SaifulHaqueNiloy/supremeai",
                               "AGENT_ROLE": "rules_breaker"})
        self.assertNotIn("GH_TOKEN", env)

    def test_unknown_role_raises(self):
        with self.assertRaises(cm.CredentialError):
            cm.build_scoped_env("warlord", token="tok")

    def test_slot_wrapper_resolves_role_from_ssot(self):
        env = cm.build_scoped_child_env("agent-1", token="tok")
        self.assertEqual(env["AGENT_ROLE"], "planner")
        env5 = cm.build_scoped_child_env("agent-5", token="tok")
        self.assertEqual(env5["AGENT_ROLE"], "ci")

    def test_scope_violation_raises(self):
        with mock.patch.object(cm, "FORBIDDEN_ENV_KEYS", {"GH_TOKEN"}), \
             self.assertRaises(cm.CredentialError):
            cm.build_scoped_env("coder", token="tok")

    def test_mask_token(self):
        masked = cm.mask_token("ghs_abcdefghijklmnop")
        self.assertTrue(masked.startswith("ghs_***"))
        self.assertNotIn("abcdefgh", masked)
        self.assertEqual(cm.mask_token(""), "")


# ───────────────────── vault fetch + JIT mint (offline) ─────────────────────

class FetchAndMintTests(unittest.TestCase):
    def setUp(self):
        self.SECRETS = {
            "AGENT_CODER_1_APP_ID": "111",
            "AGENT_CODER_1_INSTALLATION_ID": "222",
            "AGENT_CODER_1_PRIVATE_KEY": "-----BEGIN FAKE KEY-----",
        }

    def test_fetch_credentials_slot_prefix(self):
        transport = FakeTransport(self.SECRETS)
        creds = cm.fetch_credentials("agent-3", {"INFISICAL_CLIENT_ID": "c"}, transport)
        self.assertEqual(creds["app_id"], "111")
        self.assertEqual(creds["installation_id"], "222")
        self.assertEqual(creds["bot_name"], "supremeai-coder-1")
        self.assertEqual(creds["role"], "coder")

    def test_fetch_credentials_falls_back_to_default_prefix(self):
        transport = FakeTransport({
            "GITHUB_APP_ID": "1",
            "GITHUB_APP_INSTALLATION_ID": "2",
            "GITHUB_APP_PRIVATE_KEY": "k",
        })
        creds = cm.fetch_credentials("agent-1", {"INFISICAL_CLIENT_ID": "c"}, transport)
        self.assertEqual(creds["app_id"], "1")

    def test_fetch_credentials_missing_raises(self):
        transport = FakeTransport({})
        with self.assertRaises(cm.CredentialError):
            cm.fetch_credentials("agent-3", {}, transport)

    def test_mint_installation_token_offline(self):
        transport = FakeTransport({}, token="ghs_minted_token_98765")
        with mock.patch.dict(sys.modules, {"jwt": fake_jwt_module()}):
            minted = cm.mint_installation_token("app-1", "inst-9", "key", transport)
        self.assertEqual(minted["token"], "ghs_minted_token_98765")
        self.assertEqual(minted["expires_at"], int(time.time()) + 3600)
        post_urls = [u for m, u in transport.calls if m == "POST"]
        self.assertTrue(any("/access_tokens" in u for u in post_urls))
    def test_mint_failure_raises(self):
        class BadTransport(FakeTransport):
            def post(self, url, **kw):
                if "/access_tokens" in url:
                    return FakeResponse({"message": "bad JWT"})
                return super().post(url, **kw)

        with mock.patch.dict(sys.modules, {"jwt": fake_jwt_module()}), \
             self.assertRaises(cm.CredentialError):
            cm.mint_installation_token("a", "i", "k", BadTransport({}))

    def test_resolve_and_mint_for_slot_end_to_end(self):
        transport = FakeTransport(self.SECRETS, token="ghs_e2e_token_424242")
        with mock.patch.object(cm, "load_vault_env", return_value={"INFISICAL_CLIENT_ID": "c"}), \
             mock.patch.dict(sys.modules, {"jwt": fake_jwt_module()}):
            result = cm.resolve_and_mint_for_slot("agent-3", transport=transport)
        self.assertEqual(result["token"], "ghs_e2e_token_424242")
        self.assertEqual(result["role"], "coder")
        self.assertEqual(result["bot_name"], "supremeai-coder-1")
        # BOT_SLOT_CREDENTIALS re-export surface sanity (SSOT wiring)
        self.assertIn("agent-3", BOT_SLOT_CREDENTIALS)


# ───────────────────── ephemeral coder lease ─────────────────────

class EphemeralLeaseTests(unittest.TestCase):
    def setUp(self):
        self.store = Path("/tmp/test_supremeai_leases.json")
        self.store.unlink(missing_ok=True)

    def tearDown(self):
        self.store.unlink(missing_ok=True)

    def test_lease_grant_and_active_view(self):
        lease = cm.acquire_ephemeral_lease("third-party-agent", ttl=3600,
                                           lease_store=self.store)
        self.assertEqual(lease["slot"], "audit-pool")
        self.assertEqual(lease["ttl"], 3600)
        active = cm.active_leases(lease_store=self.store)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["agent"], "third-party-agent")
        self.assertNotIn("token", active[0])  # audit view is token-free

    def test_expired_leases_are_dropped(self):
        now = 1_000_000
        cm.acquire_ephemeral_lease("old-agent", ttl=600, lease_store=self.store,
                                   clock=lambda: now - 1200)
        self.assertEqual(cm.active_leases(lease_store=self.store, clock=lambda: now), [])

    def test_ttl_bounds_enforced(self):
        with self.assertRaises(cm.CredentialError):
            cm.acquire_ephemeral_lease("x", ttl=0, lease_store=self.store)
        with self.assertRaises(cm.CredentialError):
            cm.acquire_ephemeral_lease("x", ttl=7200, lease_store=self.store)

    def test_lease_store_is_json_not_token_dump(self):
        cm.acquire_ephemeral_lease("auditor-x", ttl=3600, lease_store=self.store)
        raw = self.store.read_text(encoding="utf-8")
        self.assertNotIn("token", raw.lower())
        json.loads(raw)  # valid JSON


# ───────────────────── zero-knowledge audit ─────────────────────

class ZeroKnowledgeAuditTests(unittest.TestCase):
    def test_presence_only_never_values(self):
        report = cm.audit_secret_presence(
            ["PRESENT_KEY", "ABSENT_KEY"],
            source_env={"PRESENT_KEY": "super-secret-value-xyz"},
        )
        self.assertTrue(report["ok"] is False)
        self.assertEqual(report["present_keys"], ["PRESENT_KEY"])
        self.assertEqual(report["missing_keys"], ["ABSENT_KEY"])
        # zero-knowledge contract: values never appear anywhere in the report
        self.assertNotIn("super-secret-value-xyz", json.dumps(report))

    def test_all_present_ok(self):
        report = cm.audit_secret_presence(["A"], source_env={"A": "v"})
        self.assertTrue(report["ok"])

    def test_blank_value_counts_as_missing(self):
        report = cm.audit_secret_presence(["A"], source_env={"A": "   "})
        self.assertEqual(report["missing_keys"], ["A"])


# ───────────────────── loop wiring (scoped spawn) ─────────────────────

class LoopScopedSpawnTests(unittest.TestCase):
    def test_run_work_command_with_jit_slot(self):
        from scripts.agents import continuous_agent_loop as loop

        captured = {}

        class FakeCM:
            CredentialError = cm.CredentialError

            @staticmethod
            def resolve_and_mint_for_slot(slot, **kw):
                captured["minted_slot"] = slot
                return {"token": "ghs_jit_tok", "expires_at": 999}

            @staticmethod
            def build_scoped_env(role, token="", agent_name="", slot="", **kw):
                captured["env"] = {"GH_TOKEN": token, "AGENT_ROLE": role,
                                   "AGENT_SLOT": slot, "AGENT_NAME": agent_name}
                return captured["env"]

            @staticmethod
            def run(cmd, env):
                captured["cmd"] = cmd
                captured["spawn_env"] = env
                return 7

        with mock.patch.dict(sys.modules, {"scripts.agents.credential_manager": FakeCM}):
            rc = loop.run_work_command(["python", "worker.py"], "coder", "coder-1",
                                       slot="agent-3")
        self.assertEqual(rc, 7)
        self.assertEqual(captured["minted_slot"], "agent-3")
        self.assertEqual(captured["spawn_env"]["GH_TOKEN"], "ghs_jit_tok")
        self.assertEqual(captured["spawn_env"]["AGENT_ROLE"], "coder")

    def test_run_work_command_refuses_without_any_token(self):
        from scripts.agents import continuous_agent_loop as loop

        class FakeCM:
            CredentialError = cm.CredentialError

            @staticmethod
            def resolve_and_mint_for_slot(slot, **kw):
                raise cm.CredentialError("no vault")

            @staticmethod
            def build_scoped_env(*a, **kw):
                raise AssertionError("must not be reached without a token")

            @staticmethod
            def run(cmd, env):
                raise AssertionError("must not spawn")

        with mock.patch.dict(sys.modules, {"scripts.agents.credential_manager": FakeCM}), \
             mock.patch.dict("os.environ", {}, clear=True):
            rc = loop.run_work_command(["python", "worker.py"], "coder", "coder-1")
        self.assertEqual(rc, 1)

    def test_run_work_command_falls_back_to_ambient_token(self):
        from scripts.agents import continuous_agent_loop as loop

        captured = {}

        class FakeCM:
            CredentialError = cm.CredentialError

            @staticmethod
            def resolve_and_mint_for_slot(slot, **kw):
                raise cm.CredentialError("vault down")

            @staticmethod
            def build_scoped_env(role, token="", agent_name="", slot="", **kw):
                captured["env"] = {"GH_TOKEN": token}
                return captured["env"]

            @staticmethod
            def run(cmd, env):
                return 0

        with mock.patch.dict(sys.modules, {"scripts.agents.credential_manager": FakeCM}), \
             mock.patch.dict("os.environ", {"GH_TOKEN": "ambient-tok"}, clear=True):
            rc = loop.run_work_command(["x"], "planner", "planner-1", slot="agent-1")
        self.assertEqual(rc, 0)
        self.assertEqual(captured["env"]["GH_TOKEN"], "ambient-tok")


class TestPushAsAgentAdapter(unittest.TestCase):
    """# বাংলা (#2644): push_as_agent.fetch_creds আর্গুমেন্ট অর্ডার রিগ্রেশন টেস্ট।"""

    def test_fetch_creds_accepts_both_argument_orders(self):
        from scripts.git import push_as_agent

        fake_vault = {
            "INFISICAL_CLIENT_ID": "cid",
            "INFISICAL_CLIENT_SECRET": "csec",
            "INFISICAL_PROJECT_ID": "pid",
        }

        with mock.patch("scripts.agents.credential_manager.fetch_credentials") as mock_fc:
            mock_fc.return_value = {"bot_name": "supremeai-coder-1"}

            # Standard order: (slot, vault)
            res1 = push_as_agent.fetch_creds("agent-3", fake_vault)
            self.assertEqual(res1["bot_name"], "supremeai-coder-1")
            mock_fc.assert_called_with("agent-3", fake_vault, transport=None)

            # Legacy order: (vault, slot)
            mock_fc.reset_mock()
            res2 = push_as_agent.fetch_creds(fake_vault, "agent-3")
            self.assertEqual(res2["bot_name"], "supremeai-coder-1")
            mock_fc.assert_called_with("agent-3", fake_vault, transport=None)


if __name__ == "__main__":
    unittest.main()
