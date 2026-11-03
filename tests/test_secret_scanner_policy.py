"""Tests for secret_scanner_policy (Guardian gate)."""
from __future__ import annotations

from scripts.ci.secret_scanner_policy import scan_text, scan_paths


def test_clean_text_no_findings() -> None:
    assert scan_text("x = 1\nname = 'hello'\n") == []


def test_github_pat_detected() -> None:
    token = "gh" + "p_" + "A" * 36
    findings = scan_text(f"TOKEN={token}\n")
    assert any(f["rule"] == "github_pat" for f in findings)


def test_private_key_detected() -> None:
    pk = "-----BEGIN RSA " + "PRIVATE KEY-----\nMIIE\n"
    findings = scan_text(pk)
    assert any(f["rule"] == "private_key" for f in findings)


def test_aws_key_detected() -> None:
    token = "AK" + "IA0123456789ABCDEF"
    findings = scan_text(token)
    assert any(f["rule"] == "aws_access_key" for f in findings)


def test_allowlist_suppresses() -> None:
    token = "gh" + "p_" + "A" * 36
    findings = scan_text(f"TOKEN={token}\n", allowlist=["ghp_"])
    # allowlist substring present in match -> suppressed
    assert findings == []


def test_scan_paths_reports_files(tmp_path) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n", encoding="utf-8")
    dirty = tmp_path / "dirty.py"
    dirty.write_text("TOKEN=" + "gh" + "p_" + "B" * 36 + "\n", encoding="utf-8")
    res = scan_paths([str(clean), str(dirty)])
    assert res["ok"] is False
    assert str(dirty) in res["files"]
    assert str(clean) not in res["files"]
    assert res["total"] >= 1
