"""Behaviour of `scripts/ops/zero_cost_capacity_probe.py`.

The probe exists to answer "how many free surfaces do we actually have?" before
any routing is built on top of them. Two failure modes are silent and expensive,
so they are pinned here:

* **A configured cookie is reported as a working session.** Presence is not
  liveness — a dead session would be routed to forever.
* **A secret value ends up in the report.** The probe counts keys; it must never
  echo one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ops"))

import zero_cost_capacity_probe as probe  # noqa: E402


def test_key_count_matches_the_router_pool_semantics():
    env = {"GEMINI_API_KEY": " k1 , k2 , , ", "GEMINI_API_KEY_1": "k3"}
    # `_ProviderKeyPool` splits the comma value; numbered keys are the fallback
    # convention. The probe must report what the router will actually rotate.
    assert probe.keys_for(env, ("GEMINI_API_KEY",)) == ["k1", "k2", "k3"]


def test_numbered_keys_stop_at_the_first_gap():
    assert probe.numbered_keys({"K_1": "a", "K_2": "b", "K_4": "d"}, "K") == ["a", "b"]


@pytest.mark.parametrize(
    ("status", "expected"),
    [(200, probe.ALIVE), (204, probe.ALIVE), (401, probe.EXPIRED),
     (403, probe.EXPIRED), (429, probe.CHALLENGED), (500, probe.UNKNOWN)],
)
def test_status_classification(status, expected):
    assert probe.classify(status) == expected


def test_a_configured_session_is_never_reported_as_alive():
    rows = probe.web_report({"BLAZE_SESSION_JWT": "jwt-value"})
    blaze = next(r for r in rows if r["surface"] == "blaze-claude-web")
    assert blaze["status"] == "PRESENT"
    assert blaze["status"] != probe.ALIVE
    assert "liveness" in blaze["detail"]


def test_report_never_contains_a_secret_value():
    secret = "sk-live-abcdef123456"
    env = {"OPENROUTER_API_KEY": secret, "CHATGPT_SESSION_TOKEN": secret}
    rows = probe.keyed_report(env, live=False) + probe.web_report(env)
    assert secret not in probe.render(rows, as_json=False)
    assert secret not in probe.render(rows, as_json=True)
    assert secret not in probe.mask(secret)


def test_check_mode_performs_no_network_io(monkeypatch):
    def explode(*_args, **_kwargs):  # pragma: no cover - only runs on failure
        raise AssertionError("--check must not open a connection")

    monkeypatch.setattr(probe.urllib.request, "urlopen", explode)
    rows = probe.keyed_report({"GEMINI_API_KEY": "k1"}, live=False)
    assert next(r for r in rows if r["surface"] == "gemini")["status"] == "CONFIGURED"


def test_ladder_puts_keyed_before_sessions_and_never_sells_paid():
    rows = probe.keyed_report({"GEMINI_API_KEY": "k1"}, live=False) + probe.web_report(
        {"BLAZE_SESSION_JWT": "jwt"}
    )
    rungs = [name for name, _, _ in probe.ladder(rows)]
    assert rungs[0].startswith("L0") and rungs[2].startswith("L2")
    paid = next(r for r in probe.ladder(rows) if r[0].startswith("L3"))
    assert paid[1] == "blocked by policy"


def test_strict_mode_fails_when_nothing_is_configured(monkeypatch):
    for name in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY",
                 "NVIDIA_API_KEY", "KILO_API_KEY", "KILOCODE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert probe.main(["--check", "--strict"]) == 2
    assert probe.main(["--check"]) == 0


def test_self_test_passes():
    assert probe._self_test() == 0
