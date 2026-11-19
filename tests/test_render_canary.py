#!/usr/bin/env python3
"""tests/test_render_canary.py — verification battery for Render canary smoke-checker."""

from __future__ import annotations

import io
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import render_canary


def test_parse_canary_targets_json():
    raw = '[{"name": "primary", "url": "https://example.com/live", "critical": true}]'
    parsed = render_canary.parse_canary_targets(raw)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "primary"
    assert parsed[0]["url"] == "https://example.com/live"
    assert parsed[0]["critical"] is True


def test_parse_canary_targets_unquoted_with_critical():
    raw = "[{name:mcp-tower,url:https://tower.example.com/health,critical:false},{name:api,url:https://api.example.com/healthz}]"
    parsed = render_canary.parse_canary_targets(raw)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "mcp-tower"
    assert parsed[0]["url"] == "https://tower.example.com/health"
    assert parsed[0]["critical"] is False
    assert parsed[1]["name"] == "api"
    assert parsed[1]["url"] == "https://api.example.com/healthz"


def test_render_canary_missing_env(monkeypatch, capsys):
    monkeypatch.delenv("RENDER_CANARY_URLS_JSON", raising=False)
    exit_code = render_canary.main()
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "RENDER_CANARY_URLS_JSON is not configured" in captured.err


def test_render_canary_all_success(monkeypatch, capsys):
    monkeypatch.setenv(
        "RENDER_CANARY_URLS_JSON",
        '[{"name": "primary", "url": "https://primary.example.com/health"}]',
    )
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"status": "ok"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        exit_code = render_canary.main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "OK primary: https://primary.example.com/health" in captured.out
    assert "Render canary passed for all configured authoritative targets." in captured.out


def test_render_canary_auxiliary_suspended_warns_and_passes(monkeypatch, capsys):
    monkeypatch.setenv(
        "RENDER_CANARY_URLS_JSON",
        '[{"name": "mcp-tower", "url": "https://mcp.example.com/health"},'
        ' {"name": "primary", "url": "https://primary.example.com/health"}]',
    )

    headers = {"x-render-routing": "suspend-by-user"}
    http_err = urllib.error.HTTPError(
        url="https://mcp.example.com/health",
        code=503,
        msg="Service Unavailable",
        hdrs=headers,
        fp=io.BytesIO(b"This service has been suspended by its owner."),
    )

    ok_resp = MagicMock()
    ok_resp.status = 200
    ok_resp.read.return_value = b"OK"
    ok_resp.__enter__.return_value = ok_resp

    def mock_urlopen(request, timeout):
        if "mcp" in request.full_url:
            raise http_err
        return ok_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        exit_code = render_canary.main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "WARN [Service Suspended by Owner] mcp-tower:" in captured.err
    assert "OK primary:" in captured.out
    assert "Render canary passed for all configured authoritative targets." in captured.out


def test_render_canary_critical_service_failure_blocks(monkeypatch, capsys):
    monkeypatch.setenv(
        "RENDER_CANARY_URLS_JSON",
        '[{"name": "primary", "url": "https://primary.example.com/health"}]',
    )

    http_err = urllib.error.HTTPError(
        url="https://primary.example.com/health",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=io.BytesIO(b"Internal Error"),
    )

    with patch("urllib.request.urlopen", side_effect=http_err), patch("time.sleep"):
        exit_code = render_canary.main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Render canary failed:" in captured.err
    assert "primary: HTTP Error 500: Internal Server Error" in captured.err


def test_matrix_mcp_canary_is_critical_and_rejects_redirects(monkeypatch):
    monkeypatch.setenv("RENDER_CANARY_URL", "https://replacement.onrender.com/health")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "mcp")
    monkeypatch.setenv("RENDER_CANARY_URLS_JSON", '[{"name":"old","url":"https://old.onrender.com/health"}]')
    reply = MagicMock()
    reply.status = 200
    reply.geturl.return_value = "https://old.onrender.com/health"
    reply.__enter__.return_value = reply
    with patch("urllib.request.urlopen", return_value=reply) as probe, patch("time.sleep"):
        assert render_canary.main() == 1
    assert all(call.args[0].full_url == "https://replacement.onrender.com/health" for call in probe.call_args_list)
