"""Tests for the repo path resolver.

The resolver exists because 101 tracked scripts referenced a top-level
``backend/`` directory that has never existed in this repository
(``git log --all -- backend/`` is empty). Guards built on that dead path crash
with ``FileNotFoundError`` instead of returning a verdict, and a crash read as
an exit code looks identical to a finding.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

import repo_paths  # noqa: E402
from repo_paths import (  # noqa: E402
    BACKEND_ALIAS,
    REPO_ROOT,
    RepoPathError,
    candidates,
    require,
    resolve,
)


class TestRoot:
    def test_root_is_a_repository(self):
        assert (REPO_ROOT / "scripts" / "ci").is_dir()

    def test_root_is_found_by_walking_not_counting(self):
        # `.git` is the same rule git itself uses; counting parents breaks when
        # this module moves.
        assert (REPO_ROOT / ".git").exists() or (REPO_ROOT / "pyproject.toml").exists()


class TestAliasIsJustifiedByTheTree:
    """The backend -> core alias must describe reality, not opinion."""

    def test_backend_directory_does_not_exist(self):
        assert not (REPO_ROOT / "backend").exists()

    def test_measured_evidence_rows(self):
        rows = repo_paths.alias_evidence()
        assert rows, "alias evidence must not be empty"
        for sub, under_backend, under_core in rows:
            assert under_core, f"{BACKEND_ALIAS}/{sub} should exist"
            assert not under_backend, f"backend/{sub} unexpectedly exists"

    def test_alias_target_exists(self):
        assert (REPO_ROOT / BACKEND_ALIAS).is_dir()

    def test_backend_existed_and_was_removed(self):
        """Record WHY the alias exists: backend/ was real, then renamed.

        An earlier version of this test asserted the directory had never
        existed. That was wrong — the clone was shallow and `git log` showed
        nothing. `--unshallow` revealed the deletion (commit 8c3c99e3,
        2026-11-10). The alias is a rename migration, not a workaround for a
        path that was always wrong.
        """
        out = subprocess.run(
            ["git", "log", "--oneline", "--all", "--", "backend/"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        ).stdout.strip()
        assert out, "expected backend/ to have history (was it a shallow clone?)"
        assert not (REPO_ROOT / "backend").exists(), "backend/ was recreated"

    def test_shallow_clone_would_hide_the_history(self):
        """Document the trap: a shallow clone makes --all look empty."""
        out = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        ).stdout.strip()
        # The history assertions above are only meaningful in a full clone.
        if out == "true":
            import pytest

            pytest.skip("shallow clone: backend/ history is not fetched")


class TestResolution:
    def test_resolves_existing_path(self):
        assert resolve("scripts/ci") is not None

    def test_returns_none_for_missing(self):
        assert resolve("no_such_dir_xyz/deeper") is None

    def test_literal_path_is_preferred(self):
        """If backend/ ever returns, it must win over every alias.

        The old package name was `backend/`, so an old string like
        `backend/core/config_validation.py` means `core/config_validation.py`:
        the leading segment is DROPPED, not nested. Both readings are offered,
        but the literal path is always candidate 0.
        """
        rels = [c.relative_to(REPO_ROOT).as_posix() for c in candidates("backend/api")]
        assert rels[0] == "backend/api"
        assert "api" in rels, "the de-prefixed reading must be offered"
        assert "core/api" in rels, "the segment-for-segment reading must be offered"

    def test_backend_prefix_is_dropped_not_nested(self):
        found = resolve("backend/core/config_validation.py")
        assert found is not None
        assert found.relative_to(REPO_ROOT).as_posix() == "core/config_validation.py"

    def test_alias_resolves_real_subpath(self):
        assert resolve("backend/api/routes") is not None

    def test_non_backend_paths_get_no_alias(self):
        assert len(candidates("scripts/ci")) == 1

    def test_empty_path_has_no_candidates(self):
        assert candidates("") == []

    def test_require_returns_resolved_path(self):
        assert require("backend/api").name == "api"

    def test_require_raises_with_actionable_message(self):
        try:
            require("backend/definitely_not_here_xyz")
        except RepoPathError as exc:
            assert "never existed" in str(exc)
            assert "Tried:" in str(exc)
        else:
            raise AssertionError("require() did not raise")

    def test_repo_path_error_is_a_filenotfound(self):
        # Callers that catch FileNotFoundError keep working.
        assert issubclass(RepoPathError, FileNotFoundError)


class TestDeadReferenceReport:
    def test_reports_the_measured_count(self):
        """The count must match what grep sees, not a number in the source."""
        out = subprocess.run(
            ["git", "grep", "-l", "backend/", "--", "scripts"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        ).stdout.strip().splitlines()
        expected = [line for line in out if line.endswith(".py")]
        count, files = repo_paths._dead_reference_report()
        assert count == len(expected), f"reported {count}, grep sees {len(expected)}"
        assert sorted(files) == sorted(expected)


class TestServiceEndpoints:
    """Hosts must come from config/service_registry.yaml, never from a literal.

    Six scripts used to carry their own copy of a production Render host. A
    second copy can only ever drift from the registry, and a stale health probe
    reports a healthy service as unreachable.
    """

    def test_registry_loads(self):
        specs = repo_paths.service_specs()
        assert specs, "config/service_registry.yaml did not load"
        assert "api" in specs and "mcp" in specs

    def test_every_served_service_declares_url_or_env(self):
        """A service that serves HTTP must say where it lives.

        Some entries legitimately have no endpoint: `firebase` deploys security
        rules (nothing to probe) and `ci-runner` is addressed by env only. The
        invariant is narrower and honest — anything with a `health_path` must
        be resolvable, because a health check will be pointed at it.
        """
        for sid, spec in repo_paths.service_specs().items():
            if spec.get("health_path"):
                assert spec.get("production_url") or spec.get("canonical_url_env"), (
                    f"{sid} has a health_path but declares neither "
                    "production_url nor canonical_url_env"
                )

    def test_firebase_has_no_health_endpoint(self):
        # Guards against someone "fixing" the above by inventing a URL.
        firebase = repo_paths.service_specs().get("firebase") or {}
        assert not firebase.get("health_path")
        assert not firebase.get("production_url")

    def test_endpoint_resolves_with_health_path(self):
        url = repo_paths.service_endpoint("api")
        assert url and url.startswith("https://")
        assert url.endswith(repo_paths.service_specs()["api"]["health_path"])

    def test_endpoint_can_omit_path(self):
        bare = repo_paths.service_endpoint("mcp", with_path=False)
        assert bare and not bare.endswith("/health")
        assert bare.startswith("https://")

    def test_unknown_service_returns_none(self):
        assert repo_paths.service_endpoint("no_such_service_xyz") is None

    def test_env_overrides_registry(self, monkeypatch):
        spec = repo_paths.service_specs()["api"]
        monkeypatch.setenv(spec["canonical_url_env"], "https://override.example")
        assert repo_paths.service_endpoint("api", with_path=False) == "https://override.example"

    def test_missing_registry_returns_empty_mapping(self, monkeypatch):
        monkeypatch.setattr(repo_paths, "_SERVICE_REGISTRY", REPO_ROOT / "does_not_exist.yaml")
        assert repo_paths.service_specs() == {}
        assert repo_paths.service_endpoint("api") is None

    #: Scripts converted from host literals to registry lookups in this change.
    #: Deliberately narrow: `scripts/ci` still holds ~30 references, most of
    #: them CLI usage examples inside docstrings, and a few genuine defaults
    #: (service_latency_probe, probe_live_status, deploy_doctor). Converting
    #: those is separate work with its own blast radius — this test locks in
    #: the ones actually fixed so they cannot regress.
    CONVERTED = (
        "scripts/ops/master_health_check.py",
        "scripts/ops/tower_discovery_probe.py",
        "scripts/ops/redis_quota_monitor.py",
        "scripts/ops/keepalive_scraper.py",
        "scripts/ops/ingest_project_docs.py",
        "scripts/agents/mcp_tower_client.py",
        "scripts/agents/agent_solution_memory.py",
        "scripts/knowledge/ingest_project_docs.py",
    )

    def test_converted_scripts_have_no_production_host_literal(self):
        import re

        pattern = re.compile(r"https://[a-z0-9-]+\.(onrender\.com|vercel\.app)")
        offenders = []
        for rel in self.CONVERTED:
            path = REPO_ROOT / rel
            assert path.is_file(), f"{rel} is listed as converted but does not exist"
            for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line) and not line.lstrip().startswith("#"):
                    offenders.append(f"{rel}:{num}")
        assert not offenders, f"hardcoded production hosts reappeared: {offenders}"

    def test_converted_scripts_use_the_registry(self):
        for rel in self.CONVERTED:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            assert "service_endpoint" in text, f"{rel} no longer resolves via the registry"


class TestGuardDoesNotExemptItself:
    """The policy guard must scan its own directory.

    `scripts/ci` was in the guard's IGNORE_PATHS, so the directory where the
    policy lives was the one directory exempt from it. That is how
    `supremeai-primary-node` (retired; live host is `supremeai-primary-node-5xso`)
    survived in deploy_doctor.py and service_latency_probe.py: the probes were
    pointed at a dead host and the gate could not see them.
    """

    def _guard(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "hc_guard", REPO_ROOT / "scripts" / "ci" / "check_hardcoded_deployment_config.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_scripts_ci_is_not_blanket_ignored(self):
        guard = self._guard()
        assert "scripts/ci" not in guard.IGNORE_PATHS

    def test_scripts_ci_files_are_scanned(self):
        guard = self._guard()
        target = (REPO_ROOT / "scripts" / "ci" / "deploy_doctor.py").resolve()
        assert not guard.should_ignore(target, REPO_ROOT)

    def test_doc_example_exception_covers_examples_not_defaults(self):
        import re

        guard = self._guard()
        pattern = re.compile(guard._DOC_EXAMPLE)
        examples = [
            "  python x.py --check --tower-url https://x.onrender.com",
            "  MCP_URL  (endpoint e.g. https://x.onrender.com/api)",
            "  GATEWAY_URL=https://x.onrender.com \\",
        ]
        defaults = [
            'DEFAULT_TOWER_URL = "https://x.onrender.com/mcp"',
            'url = os.getenv("R", "https://x.onrender.com")',
            '    "url": "https://x.onrender.com",',
        ]
        for line in examples:
            assert pattern.search(line), f"example not exempted: {line}"
        for line in defaults:
            assert not pattern.search(line), f"real default wrongly exempted: {line}"

    def test_retired_primary_host_is_gone_from_scripts(self):
        """`supremeai-primary-node` was retired in favour of -5xso."""
        offenders = []
        pattern = __import__("re").compile(r"supremeai-primary-node\.onrender\.com")
        for path in sorted((REPO_ROOT / "scripts").rglob("*")):
            if path.suffix not in {".py", ".sh"} or not path.is_file():
                continue
            for num, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern.search(line) and not line.lstrip().startswith("#"):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{num}")
        assert not offenders, f"retired host still referenced: {offenders}"
