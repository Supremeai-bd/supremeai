#!/usr/bin/env python3
"""Tests for tower_rpc_client — the shared MCP client extracted from 4 watchers.

The extraction matters because the four copies had drifted (``attempts`` 3 vs 4,
three docstrings each naming a different file as canonical). These tests pin the
behaviour every caller depended on, so a future edit cannot quietly change it in
one place only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ci"))

import tower_rpc_client as client  # noqa: E402


class _FakeResponse:
    def __init__(self, body: str, content_type: str = "application/json", headers=None):
        self._body = body.encode("utf-8")
        self.headers = {"Content-Type": content_type}
        self.headers.update(headers or {})

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(monkeypatch, response):
    """Replace urlopen with a recorder that returns `response`."""
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["headers"] = dict(req.headers)
        seen["payload"] = json.loads(req.data.decode("utf-8"))
        return response

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    return seen


def test_plain_json_body_is_parsed(monkeypatch):
    seen = _patch_urlopen(monkeypatch, _FakeResponse('{"jsonrpc":"2.0","id":1,"result":{}}'))
    payload, sid = client.rpc("tools/list", url="https://example.invalid/mcp")
    assert payload["result"] == {}
    assert sid is None
    assert seen["payload"]["method"] == "tools/list"


def test_sse_body_returns_last_data_line(monkeypatch):
    body = 'data: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
    _patch_urlopen(monkeypatch, _FakeResponse(body, "text/event-stream"))
    payload, _ = client.rpc("initialize", url="https://example.invalid/mcp")
    assert payload["result"] == {"ok": True}


def test_malformed_sse_line_is_skipped_not_fatal(monkeypatch):
    body = 'data: not-json\n\ndata: {"result":{"kept":1}}\n\n'
    _patch_urlopen(monkeypatch, _FakeResponse(body, "text/event-stream"))
    payload, _ = client.rpc("tools/call", url="https://example.invalid/mcp")
    assert payload["result"] == {"kept": 1}


def test_empty_body_means_accepted(monkeypatch):
    """A notification reply is empty; callers treat that as success, not error."""
    _patch_urlopen(monkeypatch, _FakeResponse("", "application/json"))
    payload, _ = client.rpc("notifications/initialized", notify=True,
                            url="https://example.invalid/mcp")
    assert payload == {"accepted": True}


def test_protocol_version_header_is_always_sent(monkeypatch):
    seen = _patch_urlopen(monkeypatch, _FakeResponse("{}"))
    client.rpc("tools/list", url="https://example.invalid/mcp")
    assert seen["headers"]["Mcp-protocol-version"] == client.PROTOCOL_VERSION


def test_session_id_is_echoed_into_next_request(monkeypatch):
    seen = _patch_urlopen(
        monkeypatch, _FakeResponse("{}", headers={"Mcp-Session-Id": "abc123"})
    )
    _, sid = client.rpc("initialize", url="https://example.invalid/mcp")
    assert sid == "abc123"

    client.rpc("tools/call", {"name": "x"}, session_id=sid,
               url="https://example.invalid/mcp")
    assert seen["headers"]["Mcp-session-id"] == "abc123"


def test_notify_omits_jsonrpc_id(monkeypatch):
    seen = _patch_urlopen(monkeypatch, _FakeResponse(""))
    client.rpc("notifications/initialized", {}, notify=True, url="https://example.invalid/mcp")
    assert "id" not in seen["payload"]


def test_unconfigured_endpoint_fails_loud(monkeypatch):
    """An empty registry resolution must raise, never silently post to ""."""
    monkeypatch.setattr(client, "tower_url", lambda: "")
    with pytest.raises(RuntimeError, match="no MCP tower URL configured"):
        client.rpc("tools/list")


def test_text_of_joins_content_parts():
    """Every dict part contributes; one without `text` contributes an empty
    string, which is why a lone non-text part yields a trailing newline. That is
    pre-existing behaviour of the four copies this replaced — pinned, not changed."""
    res = {"result": {"content": [{"text": "a"}, {"text": "b"}, {"nope": 1}]}}
    assert client.text_of(res) == "a\nb\n"
    only_text = {"result": {"content": [{"text": "a"}, {"text": "b"}]}}
    assert client.text_of(only_text) == "a\nb"


def test_text_of_tolerates_non_dict():
    assert client.text_of(None) == ""
    assert client.text_of({"result": {}}) == ""


def test_work_orders_first_rung_wins():
    """A tower that answers the 200 limit is never asked again."""
    calls = []

    def fetch_text(name, arguments):
        calls.append(arguments["limit"])
        return json.dumps({"workOrders": [{"id": 1}]})

    orders, limit = client.fetch_work_orders(fetch_text)
    assert orders == [{"id": 1}]
    assert limit == 200
    assert calls == [200]


def test_work_orders_ladder_falls_through_on_error_envelope():
    """Pre-r2 towers reject limit=200; the ladder must drop to 50."""
    seen = []

    def fetch_text(name, arguments):
        seen.append(arguments.get("limit"))
        if arguments.get("limit") == 200:
            return "argument validation failed"  # not JSON -> rung rejected
        return json.dumps({"workOrders": []})

    _, limit = client.fetch_work_orders(fetch_text)
    assert limit == 50
    assert seen == [200, 50]


def test_work_orders_all_rungs_fail_raises():
    """Exhausting the ladder must raise so the caller can fail-close."""
    def fetch_text(name, arguments):
        return json.dumps({"isError": True})

    with pytest.raises(TypeError, match="non-payload"):
        client.fetch_work_orders(fetch_text)


def test_tower_url_comes_from_the_registry(monkeypatch):
    """No literal in this module: the URL must flow from config."""
    monkeypatch.setattr(client, "svc", lambda sid, path="": "https://from-registry/mcp")
    assert client.tower_url() == "https://from-registry/mcp"
