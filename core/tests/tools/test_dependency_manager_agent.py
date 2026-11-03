"""Tests for tools/code/dependency_manager_agent.py — DependencyManagerAgent.

Wire-first coverage ramp: the module previously sat at 0% (122 statements +
36 branches unreachable-by-tests; its only entry point is the manual
scripts/run_dependency_check.py). This suite locks the behaviour of every
public method and the _run_command containment core.

CI-safety by construction (no environment assumptions, per the module's own
contracts):
- every external command (npm / pip / poetry+deptry / depcheck / pip-audit /
  npm audit) is faked at the module's own subprocess seam — the suite never
  invokes a real package manager and never touches the network;
- the AutoPRPipeline collaborator import is exercised through a sys.modules
  fake, so the heavy guardian_ai import chain is never loaded from a test and
  the ImportError fallback branch is reachable in every environment.
"""

import json
import os
import subprocess
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import tools.code.dependency_manager_agent as dma_module
from tools.code.dependency_manager_agent import DependencyManagerAgent

# --------------------------------------------------------------------------- #
# Harness                                                                     #
# --------------------------------------------------------------------------- #


class _FakePipeline:
    """Sentinel stand-in for AutoPRPipeline (import-success assertions)."""


@pytest.fixture(autouse=True)
def fake_pipeline_module(monkeypatch):
    """Make `from tools.code.auto_pr_pipeline import AutoPRPipeline` resolve to
    a fake module for every test (hermetic, environment-independent)."""
    mod = types.ModuleType("tools.code.auto_pr_pipeline")
    mod.AutoPRPipeline = _FakePipeline
    monkeypatch.setitem(sys.modules, "tools.code.auto_pr_pipeline", mod)
    return mod


class FakeRunner:
    """Scriptable stand-in for subprocess.run at the module's own seam.

    Outcomes are consumed in order; each is either an Exception instance to
    raise or a SimpleNamespace(stdout=..., stderr=..., returncode=...). When
    outcomes are exhausted a harmless empty-JSON result is returned so an
    unexpected extra call fails an assertion, not the harness.
    """

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.commands = []

    def __call__(self, command, capture_output=False, text=False, check=True):
        self.commands.append(list(command))
        outcome = (
            self.outcomes.pop(0)
            if self.outcomes
            else SimpleNamespace(stdout="{}", stderr="", returncode=0)
        )
        if isinstance(outcome, Exception):
            raise outcome
        if check and outcome.returncode != 0:
            raise subprocess.CalledProcessError(outcome.returncode, command, stderr=outcome.stderr)
        return outcome


def install_runner(monkeypatch, *outcomes) -> FakeRunner:
    """Bind a FakeRunner to the module's subprocess reference (module-attribute
    fake — the real subprocess module stays untouched for the rest of the
    process)."""
    runner = FakeRunner(*outcomes)
    monkeypatch.setattr(
        dma_module,
        "subprocess",
        SimpleNamespace(run=runner, CalledProcessError=subprocess.CalledProcessError),
    )
    return runner


def jso(payload) -> str:
    return json.dumps(payload)


@pytest.fixture
def agent():
    return DependencyManagerAgent()


# --------------------------------------------------------------------------- #
# _run_command — the JSON/containment core                                    #
# --------------------------------------------------------------------------- #


def test_run_command_parses_stdout_json(agent, monkeypatch):
    runner = install_runner(
        monkeypatch, SimpleNamespace(stdout=jso({"a": 1}), stderr="", returncode=0)
    )
    assert agent._run_command(["tool", "--json"]) == {"a": 1}
    assert runner.commands == [["tool", "--json"]]


def test_run_command_falls_back_to_stderr_json(agent, monkeypatch):
    # Some tools print their JSON payload on stderr (e.g. npm variants).
    install_runner(monkeypatch, SimpleNamespace(stdout="", stderr=jso({"b": 2}), returncode=0))
    assert agent._run_command(["tool"]) == {"b": 2}


def test_run_command_empty_output_returns_empty_dict(agent, monkeypatch):
    install_runner(monkeypatch, SimpleNamespace(stdout="", stderr="", returncode=0))
    assert agent._run_command(["tool"]) == {}


def test_run_command_missing_binary_reports_command_name(agent, monkeypatch):
    install_runner(monkeypatch, FileNotFoundError(2, "No such file or directory"))
    assert agent._run_command(["frobnicate", "--json"]) == {"error": "frobnicate not found."}


def test_run_command_called_process_error_captures_stderr(agent, monkeypatch):
    # check=True + non-zero exit -> CalledProcessError -> stderr surfaced.
    install_runner(monkeypatch, SimpleNamespace(stdout="", stderr="boom", returncode=1))
    assert agent._run_command(["tool"]) == {"error": "boom"}


def test_run_command_invalid_json_reports_error(agent, monkeypatch):
    install_runner(monkeypatch, SimpleNamespace(stdout="not-json", stderr="", returncode=0))
    assert agent._run_command(["tool"]) == {"error": "Invalid JSON output."}


def test_run_command_generic_exception_contained(agent, monkeypatch):
    install_runner(monkeypatch, RuntimeError("disk exploded"))
    assert agent._run_command(["tool"]) == {"error": "disk exploded"}


# --------------------------------------------------------------------------- #
# Outdated-dependency checks                                                  #
# --------------------------------------------------------------------------- #


def test_check_npm_dependencies_reports_outdated(agent, monkeypatch):
    payload = {"typescript": {"current": "4.9.5", "wanted": "4.9.5", "latest": "5.4.5"}}
    runner = install_runner(
        monkeypatch, SimpleNamespace(stdout=jso(payload), stderr="", returncode=0)
    )
    result = agent.check_npm_dependencies("/proj")
    assert result["success"] is True
    assert result["outdated_packages"] == payload
    assert result["count"] == 1
    assert "npm update" in result["recommendation"]
    assert runner.commands == [["npm", "outdated", "--json", "--prefix", "/proj"]]


def test_check_npm_dependencies_propagates_error(agent, monkeypatch):
    install_runner(monkeypatch, FileNotFoundError(2, "No such file"))
    result = agent.check_npm_dependencies("/proj")
    assert result == {"success": False, "error": "npm not found."}


def test_check_pip_dependencies_reports_outdated(agent, monkeypatch):
    payload = [{"name": "requests", "version": "2.28.0", "latest_version": "2.31.0"}]
    runner = install_runner(
        monkeypatch, SimpleNamespace(stdout=jso(payload), stderr="", returncode=0)
    )
    result = agent.check_pip_dependencies()
    assert result["success"] is True
    assert result["count"] == 1
    assert result["outdated_packages"] == payload
    assert runner.commands == [["pip", "list", "--outdated", "--format", "json"]]


def test_check_pip_dependencies_propagates_error(agent, monkeypatch):
    install_runner(monkeypatch, RuntimeError("pip exploded"))
    result = agent.check_pip_dependencies()
    assert result == {"success": False, "error": "pip exploded"}


# --------------------------------------------------------------------------- #
# Unused pip dependencies (deptry + poetry)                                   #
# --------------------------------------------------------------------------- #


def test_find_unused_pip_no_unused_reports_clean(agent, monkeypatch, tmp_path):
    runner = install_runner(monkeypatch, SimpleNamespace(stdout=jso([]), stderr="", returncode=1))
    result = agent.find_and_remove_unused_pip_dependencies(str(tmp_path))
    assert result == {
        "success": True,
        "removed_packages": [],
        "count": 0,
        "message": "No unused dependencies found.",
    }
    assert runner.commands == [["poetry", "run", "deptry", ".", "--output-format", "json"]]


def test_find_unused_pip_removes_only_dep002(agent, monkeypatch, tmp_path):
    deptry = [
        {"name": "foo", "error": {"code": "DEP002"}},
        {"name": "bar", "error": {"code": "DEP001"}},
        {"name": "baz", "error": {"code": "DEP002"}},
    ]
    runner = install_runner(
        monkeypatch,
        SimpleNamespace(stdout=jso(deptry), stderr="", returncode=1),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
    )
    cwd_before = os.getcwd()
    result = agent.find_and_remove_unused_pip_dependencies(str(tmp_path))
    assert result == {"success": True, "removed_packages": ["foo", "baz"], "count": 2}
    assert runner.commands == [
        ["poetry", "run", "deptry", ".", "--output-format", "json"],
        ["poetry", "remove", "foo"],
        ["poetry", "remove", "baz"],
    ]
    assert os.getcwd() == cwd_before


def test_find_unused_pip_skips_failed_removals(agent, monkeypatch, tmp_path):
    deptry = [
        {"name": "aaa", "error": {"code": "DEP002"}},
        {"name": "bbb", "error": {"code": "DEP002"}},
    ]
    install_runner(
        monkeypatch,
        SimpleNamespace(stdout=jso(deptry), stderr="", returncode=1),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
        subprocess.CalledProcessError(1, ["poetry", "remove", "bbb"], stderr="lock error"),
    )
    result = agent.find_and_remove_unused_pip_dependencies(str(tmp_path))
    assert result == {"success": True, "removed_packages": ["aaa"], "count": 1}


def test_find_unused_pip_error_restores_cwd(agent, monkeypatch, tmp_path):
    install_runner(monkeypatch, FileNotFoundError(2, "No such file"))
    cwd_before = os.getcwd()
    result = agent.find_and_remove_unused_pip_dependencies(str(tmp_path))
    assert result == {"success": False, "error": "poetry not found."}
    assert os.getcwd() == cwd_before


# --------------------------------------------------------------------------- #
# Unused npm dependencies (depcheck + npm uninstall)                          #
# --------------------------------------------------------------------------- #


def test_find_unused_npm_no_unused_reports_clean(agent, monkeypatch):
    runner = install_runner(monkeypatch, SimpleNamespace(stdout=jso({}), stderr="", returncode=1))
    result = agent.find_and_remove_unused_npm_dependencies("/proj")
    assert result == {
        "success": True,
        "removed_packages": [],
        "count": 0,
        "message": "No unused npm dependencies found.",
    }
    assert runner.commands == [["depcheck", "--json", "/proj"]]


def test_find_unused_npm_removes_each_with_prefix(agent, monkeypatch):
    runner = install_runner(
        monkeypatch,
        SimpleNamespace(stdout=jso({"dependencies": ["lodash", "chalk"]}), stderr="", returncode=1),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
    )
    result = agent.find_and_remove_unused_npm_dependencies("/proj")
    assert result == {"success": True, "removed_packages": ["lodash", "chalk"], "count": 2}
    assert runner.commands == [
        ["depcheck", "--json", "/proj"],
        ["npm", "uninstall", "lodash", "--prefix", "/proj"],
        ["npm", "uninstall", "chalk", "--prefix", "/proj"],
    ]


def test_find_unused_npm_error_with_dependencies_still_proceeds(agent, monkeypatch):
    # depcheck may exit non-zero while still emitting a valid JSON payload;
    # the guard only fails when the parsed result carries no dependency keys.
    install_runner(
        monkeypatch,
        SimpleNamespace(
            stdout=jso({"error": "stderr noise", "dependencies": ["leftpad"]}),
            stderr="",
            returncode=1,
        ),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
    )
    result = agent.find_and_remove_unused_npm_dependencies("/proj")
    assert result == {"success": True, "removed_packages": ["leftpad"], "count": 1}


def test_find_unused_npm_skips_failed_removals_and_continues(agent, monkeypatch):
    # A failing uninstall must not abort the remaining packages (loop continues).
    runner = install_runner(
        monkeypatch,
        SimpleNamespace(
            stdout=jso({"dependencies": ["goodpkg", "badpkg", "lastpkg"]}), stderr="", returncode=1
        ),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
        subprocess.CalledProcessError(1, ["npm", "uninstall", "badpkg"], stderr="npm err"),
        SimpleNamespace(stdout="{}", stderr="", returncode=0),
    )
    result = agent.find_and_remove_unused_npm_dependencies("/proj")
    assert result == {"success": True, "removed_packages": ["goodpkg", "lastpkg"], "count": 2}
    assert ["npm", "uninstall", "badpkg", "--prefix", "/proj"] in runner.commands


def test_find_unused_npm_error_without_dependency_keys_fails(agent, monkeypatch):
    install_runner(monkeypatch, FileNotFoundError(2, "No such file"))
    result = agent.find_and_remove_unused_npm_dependencies("/proj")
    assert result == {"success": False, "error": "depcheck not found."}


def test_find_unused_npm_devdependencies_only_reports_clean(agent, monkeypatch):
    # Only devDependencies present -> no "dependencies" key -> clean outcome.
    install_runner(
        monkeypatch,
        SimpleNamespace(stdout=jso({"devDependencies": ["a"]}), stderr="", returncode=1),
    )
    result = agent.find_and_remove_unused_npm_dependencies("/proj")
    assert result["success"] is True
    assert result["removed_packages"] == []


# --------------------------------------------------------------------------- #
# Vulnerability scans                                                         #
# --------------------------------------------------------------------------- #


def test_check_pip_vulnerabilities_counts_findings(agent, monkeypatch):
    payload = {"vulnerabilities": [{"id": "GHSA-xxxx", "fix_versions": ["2.31.0"]}], "fixes": []}
    runner = install_runner(
        monkeypatch, SimpleNamespace(stdout=jso(payload), stderr="", returncode=1)
    )
    result = agent.check_pip_vulnerabilities()
    assert result == {"success": True, "vulnerabilities": payload["vulnerabilities"], "count": 1}
    assert runner.commands == [["pip-audit", "--format", "json"]]


def test_check_pip_vulnerabilities_propagates_error(agent, monkeypatch):
    install_runner(monkeypatch, RuntimeError("audit exploded"))
    assert agent.check_pip_vulnerabilities() == {"success": False, "error": "audit exploded"}


def test_check_npm_vulnerabilities_passes_audit_payload(agent, monkeypatch):
    payload = {
        "vulnerabilities": {"lodash": {"severity": "high"}},
        "metadata": {"vulnerabilities": {"high": 1}},
    }
    runner = install_runner(
        monkeypatch, SimpleNamespace(stdout=jso(payload), stderr="", returncode=1)
    )
    result = agent.check_npm_vulnerabilities("/proj")
    assert result == {"success": True, "audit_results": payload}
    assert runner.commands == [["npm", "audit", "--json", "--prefix", "/proj"]]


def test_check_npm_vulnerabilities_propagates_error(agent, monkeypatch):
    install_runner(monkeypatch, FileNotFoundError(2, "No such file"))
    assert agent.check_npm_vulnerabilities("/proj") == {"success": False, "error": "npm not found."}


# --------------------------------------------------------------------------- #
# auto_update_and_pr — the async update + PR pipeline                         #
# --------------------------------------------------------------------------- #


async def test_auto_update_without_pipeline_reports_error(agent):
    agent.pr_pipeline = None
    result = await agent.auto_update_and_pr("/repo", "requests")
    assert result == {"status": "error", "message": "AutoPRPipeline not found."}


async def test_auto_update_rejects_unsupported_package_manager(agent):
    result = await agent.auto_update_and_pr("/repo", "leftpad", package_manager="cargo")
    assert result == {"status": "error", "message": "Unsupported package manager: cargo"}


async def test_auto_update_pip_failure_reports_error(agent, monkeypatch):
    install_runner(
        monkeypatch,
        subprocess.CalledProcessError(
            1, ["pip", "install", "--upgrade", "requests"], stderr="no net"
        ),
    )
    result = await agent.auto_update_and_pr("/repo", "requests")
    assert result == {"status": "error", "message": "Failed to update package: no net"}


async def test_auto_update_pip_success_creates_pr(agent, monkeypatch):
    install_runner(monkeypatch, SimpleNamespace(stdout="", stderr="", returncode=0))
    pipeline = AsyncMock(return_value={"status": "created", "pr_number": 7})
    agent.pr_pipeline = SimpleNamespace(execute_pipeline=pipeline)

    result = await agent.auto_update_and_pr("/repo", "requests")

    assert result == {"status": "created", "pr_number": 7}
    pipeline.assert_awaited_once()
    kwargs = pipeline.await_args.kwargs
    assert kwargs["repo_path"] == "/repo"
    assert (
        kwargs["branch_name"] == f"chore/update-requests-{kwargs['branch_name'].rsplit('-', 1)[1]}"
    )
    assert kwargs["branch_name"].rsplit("-", 1)[1].isdigit()
    assert kwargs["pr_title"] == "chore: Update pip dependency requests"
    assert kwargs["commit_message"] == kwargs["pr_title"]
    assert kwargs["pr_body"] == "Automatically updated `requests` to the latest version."
    assert kwargs["target_repo"] == "your-org/your-repo-name"


async def test_auto_update_npm_success_uses_npm_install_latest(agent, monkeypatch):
    runner = install_runner(monkeypatch, SimpleNamespace(stdout="", stderr="", returncode=0))
    pipeline = AsyncMock(return_value={"status": "created", "pr_number": 9})
    agent.pr_pipeline = SimpleNamespace(execute_pipeline=pipeline)

    result = await agent.auto_update_and_pr("/repo", "leftpad", package_manager="npm")

    assert result == {"status": "created", "pr_number": 9}
    assert runner.commands == [["npm", "install", "leftpad@latest", "--prefix", "/repo"]]
    kwargs = pipeline.await_args.kwargs
    assert kwargs["pr_title"] == "chore: Update npm dependency leftpad"


# --------------------------------------------------------------------------- #
# __init__ — optional-collaborator contract                                   #
# --------------------------------------------------------------------------- #


def test_init_uses_available_pipeline(fake_pipeline_module):
    agent = DependencyManagerAgent()
    assert isinstance(agent.pr_pipeline, fake_pipeline_module.AutoPRPipeline)


def test_init_survives_missing_pipeline_module(monkeypatch):
    # sys.modules[name] = None makes the import raise ImportError -> None.
    monkeypatch.setitem(sys.modules, "tools.code.auto_pr_pipeline", None)
    agent = DependencyManagerAgent()
    assert agent.pr_pipeline is None
