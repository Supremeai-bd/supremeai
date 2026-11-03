"""#1635 — agent_dashboard.py contract tests.

বাংলা: dashboard-এর pure logic যেন লাইভ GitHub ডেটা ছাড়াই যাচাইযোগ্য থাকে —
roster building (legacy + dynamic merge), claim-marker parsing, branch→slot
mapping, stale detection (>4h claim without PR), আর টেবিল রেন্ডারিং।
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "agents" / "agent_dashboard.py"
REGISTRY = Path(__file__).resolve().parents[3] / "docs" / "master_docs" / "AGENT_SLOT_REGISTRY.yaml"

_spec = importlib.util.spec_from_file_location("agent_dashboard", SCRIPT)
ad = importlib.util.module_from_spec(_spec)
sys.modules["agent_dashboard"] = ad
_spec.loader.exec_module(ad)


NOW = datetime(2026, 9, 27, 14, 40, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# ─────────────────────────────────────────────────────── registry roster ──
class TestRoster:
    def test_script_exists(self):
        assert SCRIPT.exists()

    def test_registry_loads_and_roster_built(self):
        registry = ad.load_registry(REGISTRY)
        roster = ad.build_roster(registry)
        names = [s.name for s in roster]
        # Legacy slots from the registry (issue #1635 mock uses these).
        assert "agent-3" in names
        agent3 = next(s for s in roster if s.name == "agent-3")
        assert agent3.role == "coder-1"
        # Branch tokens must cover both legacy + post-migration naming.
        assert agent3.matches_branch("coder-1-issue-1635")
        assert agent3.matches_branch("agent-3-coder-1")
        # ROOT-CAUSE #2723-চুক্তি-পিন: agent-1/agent-2 live-tower থেকে
        # decommissioned (active: false, registry: "absent from live tower as
        # of 2026-09-30") — roster শুধু active slot-ই বহন করে।
        assert "agent-1" not in names
        assert "agent-2" not in names

    def test_dynamic_slot_merges_into_legacy(self):
        registry = {
            "role_pools": {"coder": {"branch_pattern": "coder-{N}"}},
            "slots": [
                {"slot": "agent-3", "tool": "coder-1", "active": True, "branch": "agent-3-coder-1"}
            ],
        }
        roster = ad.build_roster(registry)
        extra = ad.discover_dynamic_slots(registry, ["coder-1-issue-1635", "coder-7-wip"], roster)
        names = [s.name for s in roster]
        # coder-1 merges into agent-3 (legacy_migration_target), coder-7 is new.
        assert names.count("agent-3") == 1 and "coder-1" not in names
        assert "coder-7" in names
        assert any(s.name == "coder-7" for s in extra)

    def test_dynamic_slot_number_extraction(self):
        registry = {"role_pools": {"coder": {"branch_pattern": "coder-{N}"}}}
        roster = ad.build_roster(registry)
        ad.discover_dynamic_slots(registry, ["coder-1-issue-1635"], roster)
        coder1 = next(s for s in roster if s.role == "coder")
        assert coder1.name == "coder-1"


# ─────────────────────────────────────────────────────── claim matching ──
class TestClaimMatching:
    def test_identity_match_variants(self):
        s = ad.Slot("agent-3", "coder-1")
        assert s.matches_claimant("agent-3-coder-1")
        assert s.matches_claimant("agent-3")
        assert s.matches_claimant("coder-1")  # post-migration name
        assert s.matches_claimant("supremeai-coder-1-bot")
        assert not s.matches_claimant("agent-6-coder-2")
        assert not s.matches_claimant("")

    def test_pool_role_token_never_phantom_matches(self):
        """Regression: pool-name token 'coder' must not glom onto
        'agent-3-coder-1' — that spawned phantom claims on every dynamic
        coder slot in the first live run."""
        s = ad.Slot("coder-5", "coder")
        assert not s.matches_claimant("agent-3-coder-1")
        assert s.matches_claimant("coder-5")
        assert s.matches_claimant("coder-5-something")

    def test_bot_identity_token(self):
        s = ad.Slot("agent-2", "pr-helper-1", "supremeai-pr-helper[bot]")
        assert s.matches_claimant("supremeai-pr-helper")


# ─────────────────────────────────────────────────────── marker parsing ──
class TestMarkerParsing:
    MARKER = (
        "### 🔒 Atomic Claim Established (GAP-01)\n\n"
        "- **Agent:** `agent-3-coder-1`\n"
        "- **Issue:** #1635\n"
        "- **Claimed at:** 2026-09-27T09:20:00Z\n"
        "- **Method:** Claim-then-Verify (Compare-And-Swap)"
    )

    def test_claim_agent_and_time_parsed(self):
        m = ad.CLAIM_AGENT_RE.search(self.MARKER)
        t = ad.CLAIM_TIME_RE.search(self.MARKER)
        assert m.group(1) == "agent-3-coder-1"
        assert "2026-09-27T09:20:00Z" in t.group(1)

    def test_age_hours(self):
        claimed = NOW - timedelta(hours=2)
        hrs = ad.age_hours(_iso(claimed), NOW)
        assert abs(hrs - 2.0) < 1 / 60
        assert ad.fmt_age(0.5) == "30m"
        assert ad.fmt_age(2.0) == "2h"

    def test_age_hours_naive_timestamp_assumed_utc(self):
        """#2134: naive (zone-less) markers must not raise TypeError."""
        hrs = ad.age_hours("2026-09-27 12:40:00", NOW)  # naive, space-separated
        assert abs(hrs - 2.0) < 1 / 60

    def test_parse_iso_naive_gets_utc_tzinfo(self):
        dt = ad.parse_iso("2026-09-27 12:40:00")
        assert dt is not None and dt.tzinfo is not None

    def test_parse_iso_z_suffix_still_aware(self):
        dt = ad.parse_iso("2026-09-27T12:40:00Z")
        assert dt is not None and dt.tzinfo is not None


# ────────────────────────────────────────────────────────── row building ──
def _roster():
    return ad.build_roster(ad.load_registry(REGISTRY))


class TestBuildRows:
    def test_active_claim_with_pr(self):
        agent3 = next(s for s in _roster() if s.name == "agent-3")
        claims = [
            {
                "issue": 1635,
                "title": "t",
                "created_at": _iso(NOW),
                "agent": "agent-3-coder-1",
                "claimed_at": _iso(NOW - timedelta(hours=1)),
            }
        ]
        prs = [{"number": 2200, "headRefName": "coder-1-issue-1635", "title": "t"}]
        rows, warnings = ad.build_rows([agent3], claims, prs, NOW, 4.0)
        r = rows[0]
        assert r["status"] == "ACTIVE" and r["issue"] == "#1635" and r["pr"] == "#2200"
        assert r["age"] == "1h" and not warnings

    def test_stale_claim_without_pr(self):
        agent3 = next(s for s in _roster() if s.name == "agent-3")
        claims = [
            {
                "issue": 999,
                "title": "t",
                "created_at": _iso(NOW),
                "agent": "agent-3-coder-1",
                "claimed_at": _iso(NOW - timedelta(hours=6)),
            }
        ]
        rows, warnings = ad.build_rows([agent3], claims, [], NOW, 4.0)
        assert rows[0]["status"] == "STALE" and rows[0]["stale"] is True
        assert any("stale lock" in w for w in warnings)

    def test_claim_just_under_threshold_not_stale(self):
        agent3 = next(s for s in _roster() if s.name == "agent-3")
        claims = [
            {
                "issue": 999,
                "title": "t",
                "created_at": _iso(NOW),
                "agent": "agent-3-coder-1",
                "claimed_at": _iso(NOW - timedelta(hours=3, minutes=59)),
            }
        ]
        rows, warnings = ad.build_rows([agent3], claims, [], NOW, 4.0)
        assert rows[0]["status"] == "ACTIVE" and not warnings

    def test_idle_slot_and_unknown_claimant(self):
        # ROOT-CAUSE #2723: agent-1 decommissioned — roster-এ নেই; যেকোনো
        # active slot দিয়ে idle+unknown-claimant চুক্তি অনুশীলন যায়।
        agent4 = next(s for s in _roster() if s.name == "agent-4")
        claims = [
            {"issue": 500, "title": "t", "created_at": _iso(NOW), "agent": None, "claimed_at": None}
        ]
        rows, warnings = ad.build_rows([agent4], claims, [], NOW, 4.0)
        assert rows[0]["status"] == "IDLE"
        assert any("no roster-matched claimant" in w for w in warnings)

    def test_multiple_claims_flagged(self):
        agent3 = next(s for s in _roster() if s.name == "agent-3")

        def mk(n):
            return {
                "issue": n,
                "title": "t",
                "created_at": _iso(NOW),
                "agent": "agent-3-coder-1",
                "claimed_at": _iso(NOW),
            }

        rows, warnings = ad.build_rows([agent3], [mk(1), mk(2)], [], NOW, 4.0)
        assert any("multiple claims" in w for w in warnings)


# ─────────────────────────────────────────────────────────── rendering ──
class TestRendering:
    def test_table_contains_columns_and_header(self):
        rows = [
            {
                "slot": "agent-3-coder-1",
                "role": "coder-1",
                "status": "ACTIVE",
                "issue": "#1635",
                "pr": "—",
                "age": "2h",
                "stale": False,
            }
        ]
        out = ad.render_table(rows, NOW)
        assert "AGENT DASHBOARD — 2026-09-27 14:40 UTC" in out
        for col in ("Slot", "Role", "Status", "Issue", "PR", "Age"):
            assert col in out
        assert "agent-3-coder-1" in out and "#1635" in out and "ACTIVE" in out

    def test_role_labels_keep_columns_aligned(self):
        assert ad.role_label("planner-and-auditor") == "Planner"
        assert ad.role_label("coder-1") == "Coder"
        assert ad.role_label("ci-action") == "CI/CD"
        assert len(ad.role_label("some-very-long-role-name")) <= 13

    def test_idle_dynamic_slots_collapse_to_summary(self):
        rows = [
            {
                "slot": f"coder-{n}",
                "role": "coder",
                "status": "IDLE",
                "issue": "—",
                "pr": "—",
                "age": "—",
                "stale": False,
            }
            for n in range(5, 9)
        ] + [
            {
                "slot": "agent-1",
                "role": "planner",
                "status": "IDLE",
                "issue": "—",
                "pr": "—",
                "age": "—",
                "stale": False,
            }
        ]
        out = ad.render_table(rows, NOW)
        assert "+ 4 idle pool slots" in out
        assert "coder-5" in out and "coder-8" not in out  # collapsed, not rows
        assert "agent-1" in out  # legacy always shows

    def test_offline_note(self):
        out = ad.render_table([], NOW, offline=True)
        assert "offline mode" in out

    def test_warnings_rendered(self):
        assert "boom" in ad.render_warnings(["boom"])


# ────────────────────────────────────────────────────────── live smoke ──
class TestLiveSmoke:
    def test_offline_dashboard_end_to_end(self):
        data = ad.collect_dashboard(REGISTRY, now=NOW, offline=True)
        assert data["offline"] is True
        assert any(r["slot"] == "agent-3" for r in data["rows"])
        json.dumps(data)  # must be JSON-serializable

    def test_cli_runs_zero_exit(self):
        import subprocess

        res = subprocess.run(
            [sys.executable, str(SCRIPT), "--offline"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert res.returncode == 0, res.stderr
        assert "AGENT DASHBOARD" in res.stdout


# ─────────────────────────────────────────── gh_available liveness (#2134) ──
class TestGhAvailable:
    """GH_TOKEN presence must NOT count as authentication."""

    def test_bogus_token_reports_unavailable(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "ghs_definitely_invalid_token")
        # gh() shells out to the real binary; with a bogus token `gh api user`
        # exits non-zero -> "" -> gh_available() must be False.
        assert ad.gh_available() is False

    def test_no_token_no_gh_binary(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.setattr(ad, "gh", lambda *a, **k: "")
        assert ad.gh_available() is False

    def test_valid_token_reports_available(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "ghs_valid")
        monkeypatch.setattr(
            ad,
            "gh",
            lambda *a, **k: "somebody" if a[:2] == ("api", "user") else "",
        )
        assert ad.gh_available() is True

    def test_gh_version_no_longer_satisfies_token_path(self, monkeypatch):
        """Regression pin: `--version` succeeding must NOT equal available."""
        monkeypatch.setenv("GH_TOKEN", "ghs_expired_token")

        def fake_gh(*args, **kwargs):
            if args and args[0] == "--version":
                return "gh version 2.63.0"  # binary present...
            return ""  # ...but every authenticated call fails

        monkeypatch.setattr(ad, "gh", fake_gh)
        assert ad.gh_available() is False
