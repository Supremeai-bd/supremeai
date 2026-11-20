import io
import json

import pytest
from scripts.ci import mcp_tower_conformance_probe as probe
from scripts.ci.mcp_tower_conformance_probe import (
    analyze_capabilities,
    build_initialize_payload,
    run_self_test,
)


def test_mcp_tower_conformance_probe_self_test():
    assert run_self_test() == 0

def test_initialize_payload_contract():
    p1 = build_initialize_payload("2025-06-18")
    assert p1["jsonrpc"] == "2.0"
    assert p1["id"] == "probe-2025-06-18"
    assert p1["params"]["protocolVersion"] == "2025-06-18"
    assert p1["params"]["clientInfo"]["name"] == "supremeai-conformance-probe"

def test_capability_analysis_matrix():
    raw_caps = {
        "tools": {"listChanged": True},
        "resources": {"listChanged": True},
        "prompts": {"listChanged": True}
    }
    analysis = analyze_capabilities(raw_caps)
    assert analysis["tools"] is True
    assert analysis["resources"] is True
    assert analysis["prompts"] is True
    assert analysis["tasks"] is False
    assert analysis["elicitation"] is False
    assert analysis["sampling"] is False
    assert analysis["logging"] is False
    assert analysis["completions"] is False

    expanded = {
        "tools": {},
        "tasks": {"listChanged": True},
        "elicitation": {}
    }
    analysis2 = analyze_capabilities(expanded)
    assert analysis2["tasks"] is True
    assert analysis2["elicitation"] is True
    assert analysis2["resources"] is False


@pytest.mark.parametrize("kind", ["json", "sse", "rpc_error", "wrong_id", "missing_result"])
def test_handshake_requires_matching_result_and_releases_session(monkeypatch, kind):
    version = "2025-11-25"
    result = {"protocolVersion": version, "serverInfo": {"name": "tower", "version": "1"}, "capabilities": {}}
    msg = {"jsonrpc": "2.0", "id": f"probe-{version}", "result": result}
    if kind == "rpc_error":
        msg["error"] = {"code": -32000}
    elif kind == "wrong_id":
        msg["id"] = "different"
    elif kind == "missing_result":
        del msg["result"]
    calls = []

    def open_request(req, timeout):
        calls.append(req)
        body = json.dumps(msg)
        if kind == "sse":
            body = f": heartbeat\n\ndata: \n\ndata: {body}\n\n"
        response = io.BytesIO(body.encode())
        response.status = 200
        response.headers = {"Content-Type": "text/event-stream" if kind == "sse" else "application/json",
                            "Mcp-Session-Id": "private-test-session"}
        return response

    monkeypatch.setattr(probe.urllib.request, "urlopen", open_request)
    report = probe.probe_version("http://localhost/mcp", version)
    assert report["ok"] == (kind in {"json", "sse"})
    assert [req.method for req in calls] == ["POST", "DELETE"]
    assert calls[-1].get_header("Mcp-session-id") == "private-test-session"
    assert report["sessionClosed"] and "private-test-session" not in json.dumps(report)
