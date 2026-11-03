import pytest

from tools.social.marketplace_agent import MarketplaceAgent

# FIX(#1097): module-level skip removed; tests re-triaged against the REAL
# agent contract (tools/social/marketplace_agent.py):
#   - search_marketplaces() hits the live PyPI/npm registry APIs and returns
#     name/marketplace/version/install_cmd/description/license/home_page.
#     There is NO "stars" key and no min_stars filter in the current contract
#     (registry search APIs don't expose stars without extra GitHub calls), so
#     the filter test now exercises the supported `license` filter instead.
#   - install_tool(sandbox=True) runs DockerSandbox — unit tests mock it
#     (no docker daemon / no real package installs in CI).


def test_marketplace_search():
    agent = MarketplaceAgent()
    results = agent.search_marketplaces("pdf", categories=["npm"])
    assert isinstance(results, list)
    assert all(r["marketplace"] == "npm" for r in results)
    # Real registry contract: each result carries the documented keys.
    for r in results:
        assert "name" in r and "install_cmd" in r


def test_marketplace_search_license_filter():
    agent = MarketplaceAgent()
    # `license` is the filter key the agent actually honors
    # (tools/social/marketplace_agent.py — filters block).
    results = agent.search_marketplaces("pdf", categories=["npm"], filters={"license": ["MIT"]})
    for r in results:
        assert r.get("license") == "MIT"


def test_marketplace_install_sandboxed(monkeypatch):
    agent = MarketplaceAgent()

    class FakeSandbox:
        def __init__(self, image=None):
            self.image = image

        def execute_command(self, cmd):
            return {"success": True, "stdout": f"mocked install: {cmd}"}

    monkeypatch.setattr("tools.devops.docker_sandbox.DockerSandbox", FakeSandbox, raising=False)
    res = agent.install_tool("npm:pdf-parse", "supremeai-worker-01", sandbox=True)
    assert res["success"] is True
    assert res["sandboxed"] is True
    assert res["status"] == "verified_and_installed"
    assert res["tool_id"] == "npm:pdf-parse"


def test_marketplace_install_sandbox_error_is_reported(monkeypatch):
    agent = MarketplaceAgent()

    class ExplodingSandbox:
        def __init__(self, image=None):
            raise RuntimeError("no docker daemon in unit tests")

    monkeypatch.setattr(
        "tools.devops.docker_sandbox.DockerSandbox", ExplodingSandbox, raising=False
    )
    res = agent.install_tool("npm:pdf-parse", "supremeai-worker-01", sandbox=True)
    # Fail-closed contract: sandbox failure must NOT be reported as success.
    assert res["success"] is False
    assert res["sandboxed"] is True
