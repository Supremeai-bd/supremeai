"""Legacy shared knowledge must fail closed until independently reviewed."""
import json
from unittest.mock import Mock

import pytest

from scripts.ci import ai_knowledge_exchange as exchange
from scripts.ci import ingest_pr_knowledge as ingest


def packet():
    return {"agent_name": "fixture", "topic": "example", "insight": "This is an unreviewed sample insight."}


def body():
    return exchange.SHARE_MARKER_OPEN + json.dumps(packet()) + exchange.SHARE_MARKER_CLOSE


def envelope():
    obj = {"schema": "pr-knowledge-envelope/2", "role": "coder", "knowledge": {
        "fix_mechanism": "fixture", "why_this_way": "fixture", "alternatives_rejected": ["fixture"], "pitfalls_to_avoid": ["fixture"],
    }}
    return ingest.MARKER_OPEN_V2 + json.dumps(obj) + ingest.MARKER_CLOSE_V2


def test_direct_packet_never_writes_even_with_credentials(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://invalid.example")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fixture")
    http = Mock(side_effect=AssertionError("network not allowed"))
    monkeypatch.setattr(exchange, "_http_json", http)
    normalized = exchange.normalize_share_packet(packet())
    assert normalized is not None
    assert exchange.persist_shared_packet(normalized) is False
    assert exchange.persist_shared_packet(normalized, dry_run=True) is True
    assert exchange.persist_shared_packet({"insight": "x"}, dry_run=True) is False
    assert exchange.main(["--share-json", json.dumps(packet())]) == 1
    assert exchange.main(["--share-json", json.dumps(packet()), "--dry-run"]) == 0
    stdout = capsys.readouterr().out
    assert "unreviewed sample insight" not in stdout
    assert "nothing was stored" in stdout
    http.assert_not_called()


def test_pr_validates_without_any_remote_or_vector_write(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://invalid.example")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fixture")
    monkeypatch.setenv("QDRANT_URL", "https://invalid.example")
    monkeypatch.setenv("GEMINI_API_KEY", "fixture")
    save = Mock(side_effect=AssertionError("no writes"))
    embed = Mock(side_effect=AssertionError("no embedding"))
    monkeypatch.setattr(ingest, "post_to_supabase", save)
    monkeypatch.setattr(ingest, "generate_embedding_gemini", embed)
    assert ingest.run_ingest(1, body() + envelope()) is False
    assert ingest.run_ingest(1, body() + envelope(), dry_run=True) is True
    assert "unreviewed sample insight" not in capsys.readouterr().out
    save.assert_not_called()
    embed.assert_not_called()


@pytest.mark.parametrize("invalid", [
    exchange.SHARE_MARKER_OPEN + "not json" + exchange.SHARE_MARKER_CLOSE,
    exchange.SHARE_MARKER_OPEN + "{}",
    ingest.MARKER_OPEN_V2 + "not json" + ingest.MARKER_CLOSE_V2,
    ingest.MARKER_OPEN_V2 + "{}",
    ingest.MARKER_OPEN_V2 + "[]" + ingest.MARKER_CLOSE_V2,
    envelope() + ingest.MARKER_OPEN_V2,
    envelope() + envelope(),
    envelope() + ingest.MARKER_OPEN_V1 + "{}" + ingest.MARKER_CLOSE_V1,
    ingest.MARKER_CLOSE_V2 + "{}" + ingest.MARKER_OPEN_V2,
    body() + exchange.SHARE_MARKER_CLOSE,
])
def test_malformed_evidence_does_not_succeed(invalid):
    assert ingest.run_ingest(1, invalid, dry_run=True) is False
    assert ingest.run_ingest(1, invalid) is False


def test_issue_scan_fails_closed_on_read_errors_and_truncation(monkeypatch):
    fetch = Mock(side_effect=RuntimeError("offline"))
    monkeypatch.setattr(exchange, "_gh_api_get", fetch)
    assert exchange.main(["--scan-issue", "3", "--repo", "owner/repo", "--dry-run"]) == 1
    fetch.side_effect = [{"number": 3}, [{}] * 100]
    assert exchange.main(["--scan-issue", "3", "--repo", "owner/repo", "--dry-run"]) == 1
    fetch.reset_mock()
    assert exchange.main(["--scan-issue", "3", "--repo", "owner/repo"]) == 1
    fetch.assert_not_called()


def test_issue_scan_validation_only_does_not_export_raw(monkeypatch, capsys):
    fetch = Mock(side_effect=[{"number": 3, "body": body()}, []])
    monkeypatch.setattr(exchange, "_gh_api_get", fetch)
    assert exchange.main(["--scan-issue", "3", "--repo", "owner/repo", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "unreviewed sample insight" not in out
    assert "none stored or approved" in out


def test_pr_cli_github_failure_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(ingest.sys, "argv", ["ingest_pr_knowledge.py", "--pr-num", "42"])
    monkeypatch.setattr(ingest.subprocess, "run", Mock(side_effect=OSError("offline")))
    assert ingest.main() == 1
    assert "nothing stored" in capsys.readouterr().err


def test_legacy_briefing_is_not_read_or_exported(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://invalid.example")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fixture")
    http = Mock(side_effect=AssertionError("no network"))
    monkeypatch.setattr(exchange, "_http_json", http)
    target = tmp_path / "out.json"
    assert exchange.main(["--export-briefing", "--output", str(target)]) == 1
    assert not target.exists()
    http.assert_not_called()