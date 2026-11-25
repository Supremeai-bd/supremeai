# -*- coding: utf-8 -*-
"""Unit tests for scripts/ci/render_mesh_parity.py (mesh-wide Render release parity gate).

# বাংলা মন্তব্য: রেন্ডার মেশ প্যারিটি গেটের অফলাইন ইউনিট টেস্ট - Git এবং Render API
# মক করে সব স্ট্যাটাস পাথ (verified, drift, no_credential, skipped, fail-open) যাচাই করা হয়।
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch
import pytest

from scripts.ci import render_mesh_parity


def test_fail_open_flag(monkeypatch):
    monkeypatch.delenv("MESH_PARITY_FAIL_OPEN", raising=False)
    assert not render_mesh_parity.fail_open()

    monkeypatch.setenv("MESH_PARITY_FAIL_OPEN", "1")
    assert render_mesh_parity.fail_open()

    monkeypatch.setenv("MESH_PARITY_FAIL_OPEN", "0")
    assert not render_mesh_parity.fail_open()


def test_env_first(monkeypatch):
    monkeypatch.delenv("KEY_A", raising=False)
    monkeypatch.delenv("KEY_B", raising=False)
    assert render_mesh_parity.env_first("KEY_A", "KEY_B") == ""

    monkeypatch.setenv("KEY_B", "value_b")
    assert render_mesh_parity.env_first("KEY_A", "KEY_B") == "value_b"

    monkeypatch.setenv("KEY_A", "value_a")
    assert render_mesh_parity.env_first("KEY_A", "KEY_B") == "value_a"


def test_path_hit():
    assert render_mesh_parity.path_hit(["core/main.py"], ["core/*"])
    assert not render_mesh_parity.path_hit(["browser/app.py"], ["core/*"])
    assert render_mesh_parity.path_hit(["docs/index.md"], ["*.md", "docs/*"])


def test_load_render_services():
    services = render_mesh_parity.load_render_services()
    assert isinstance(services, list)
    assert len(services) > 0
    for s in services:
        assert s.get("platform") == "render"
        assert s.get("status") != "retired"
        assert "name" in s


def test_main_skipped_when_no_service_ids(monkeypatch, capsys):
    # বাংলা মন্তব্য: কোনো সার্ভিস আইডি এনভ না থাকলে সব সার্ভিস skipped হিসেবে মার্ক হবে এবং পাস করবে
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("MESH_PARITY_FAIL_OPEN", raising=False)

    for env_var in [
        "RENDER_API_SERVICE_ID", "RENDER_SCRAPER_SERVICE_ID", "RENDER_MCP_SERVICE_ID",
        "RENDER_CORE_SERVICE_ID", "RENDER_WORKER_SERVICE_ID", "RENDER_BRAIN_SERVICE_ID",
        "RENDER_CI_RUNNER_SERVICE_ID"
    ]:
        monkeypatch.delenv(env_var, raising=False)

    with patch("scripts.ci.render_mesh_parity.subprocess.run") as mock_run:
        mock_proc = Mock()
        mock_proc.stdout = "1234567890abcdef1234567890abcdef12345678\n"
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        code = render_mesh_parity.main()
        assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["blocking"] == 0
    assert all(r["status"] == "skipped" for r in data["rows"])


def test_main_blocking_on_drift(monkeypatch, capsys):
    # বাংলা মন্তব্য: সার্ভিস আইডি থাকলে এবং লাইভ কমিট ও এক্সপেক্টেড কমিট অসঙ্গতিপূর্ণ হলে গেট ব্লক হবে
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("MESH_PARITY_FAIL_OPEN", raising=False)
    monkeypatch.setenv("RENDER_API_SERVICE_ID", "srv-12345")
    monkeypatch.setenv("RENDER_API_KEY", "rnd_test_key")

    sha_expected = "a" * 40
    sha_drift = "b" * 40

    with patch("scripts.ci.render_mesh_parity.load_render_services") as mock_services:
        mock_services.return_value = [{
            "name": "api",
            "canonical_service_id_env": "RENDER_API_SERVICE_ID",
            "canonical_api_key_env": "RENDER_API_KEY",
            "watch_paths": ["gateway/*"],
            "exclude_paths": [],
        }]

        with patch("scripts.ci.render_mesh_parity.path_expected_commit", return_value=sha_expected):
            with patch("scripts.ci.render_mesh_parity.RenderClient"):
                with patch("scripts.ci.render_mesh_parity.latest_live", return_value=({"status": "live", "commit": {"id": sha_drift}}, "")):
                    with patch("scripts.ci.render_mesh_parity.is_ancestor", return_value=False):
                        with patch("scripts.ci.render_mesh_parity.subprocess.run") as mock_run:
                            mock_proc = Mock()
                            mock_proc.stdout = "c" * 40 + "\n"
                            mock_proc.returncode = 0
                            mock_run.return_value = mock_proc

                            # Without fail-open: should return 1
                            code = render_mesh_parity.main()
                            assert code == 1

                            # With fail-open: should return 0 with warning
                            monkeypatch.setenv("MESH_PARITY_FAIL_OPEN", "1")
                            code_fail_open = render_mesh_parity.main()
                            assert code_fail_open == 0


def test_main_ci_runner_auxiliary_skipped(monkeypatch, capsys):
    # বাংলা মন্তব্য: ci-runner সার্ভিস সাসপেন্ডেড হওয়ায় অটো-ডেপ্লয় থেকে বাদ থাকে (plan_render_deploys.py:69)
    # তাই প্যারিটি গেটে এটি ড্রিফ্ট তৈরি না করে সরাসরি skipped হিসেবে গণ্য হবে
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("MESH_PARITY_FAIL_OPEN", raising=False)
    monkeypatch.setenv("RENDER_CI_RUNNER_SERVICE_ID", "srv-ci-runner-123")
    monkeypatch.setenv("RENDER_API_KEY_PAYKARI", "rnd_test_key")

    with patch("scripts.ci.render_mesh_parity.load_render_services") as mock_services:
        mock_services.return_value = [{
            "name": "ci-runner",
            "canonical_service_id_env": "RENDER_CI_RUNNER_SERVICE_ID",
            "canonical_api_key_env": "RENDER_API_KEY_PAYKARI",
            "watch_paths": ["scripts/ci/**"],
            "exclude_paths": [],
        }]

        with patch("scripts.ci.render_mesh_parity.path_expected_commit", return_value="a" * 40):
            with patch("scripts.ci.render_mesh_parity.subprocess.run") as mock_run:
                mock_proc = Mock()
                mock_proc.stdout = "c" * 40 + "\n"
                mock_proc.returncode = 0
                mock_run.return_value = mock_proc

                code = render_mesh_parity.main()
                assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["blocking"] == 0
    assert data["rows"][0]["status"] == "skipped"
    assert "suspended by owner" in data["rows"][0]["detail"]
