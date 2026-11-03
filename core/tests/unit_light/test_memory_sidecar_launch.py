"""Issue #1441 — memory sidecar launch-path contract guards.

The documented launch path for ``backend/memory/mcp_server.py`` broke twice:

* ``infrastructure/mcp-control-plane/mcp_config.local.json`` pointed at
  ``uv run --directory backend``, but ``backend/pyproject.toml`` declares
  dependencies only in the Poetry ``[tool.poetry.dependencies]`` table
  (``package-mode = false``). uv reads the PEP 621 ``[project]`` table —
  which does not exist — so it resolved an *empty* environment, silently
  "succeeded", and ``import mcp`` exploded with ModuleNotFoundError.
* The Render build installed uv via buildCommand, but Render does not
  persist build-phase installs to the runtime service → ``spawn uv ENOENT``
  (verified live on the tower via ``memory_status``).

These guards pin the repaired contracts so neither path can silently
regress:

1. the local example config must launch the sidecar through Poetry — the
   canonical backend dependency manager, which already declares ``mcp``;
2. ``mcp`` must stay declared in the backend Poetry dependencies;
3. the Render buildCommand must provision the persisted ``backend/.venv``
   that the tower's ``MemorySubAdapter`` prefers at spawn time.
"""

import json
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
MCP_CONFIG = REPO_ROOT / "infrastructure" / "mcp-control-plane" / "mcp_config.local.json"
RENDER_YAML = REPO_ROOT / "infrastructure" / "mcp-control-plane" / "render.yaml"

# Launch contract fixed by #1441: poetry -C backend run python memory/mcp_server.py
_EXPECTED_LAUNCH = ["-C", "backend", "run", "python", "memory/mcp_server.py"]


def _memory_sidecar_entry() -> dict:
    config = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    servers = config.get("mcpServers") or {}
    entry = servers.get("supremeai-memory")
    assert entry, "mcp_config.local.json must keep the 'supremeai-memory' sidecar entry"
    return entry


def test_memory_sidecar_launches_via_poetry():
    """The documented local launch must resolve the real Poetry env (#1441)."""
    entry = _memory_sidecar_entry()
    assert entry.get("command") == "poetry", entry
    args = [str(a) for a in entry.get("args") or []]
    assert args == _EXPECTED_LAUNCH, args


def test_memory_sidecar_never_launches_via_bare_uv():
    """Regression pin: uv resolves an EMPTY env for backend (no [project] table)."""
    entry = _memory_sidecar_entry()
    assert entry.get("command") != "uv", entry
    joined = " ".join(str(a) for a in entry.get("args") or [])
    assert "--directory" not in joined, joined


def test_mcp_package_declared_in_backend_poetry_deps():
    """The sidecar's only hard third-party import is ``mcp`` — keep it declared."""
    data = tomllib.loads((BACKEND_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    assert "mcp" in deps, "mcp disappeared from [tool.poetry.dependencies]"


def test_render_build_provisions_persisted_backend_venv():
    """Render must bake backend/.venv at build time — the runtime has no uv."""
    text = RENDER_YAML.read_text(encoding="utf-8")
    assert "uv venv ../../backend/.venv" in text
    assert 'uv pip install --python ../../backend/.venv/bin/python "mcp' in text


@pytest.mark.parametrize(
    "sidecar_key",
    ["supremeai-control-tower", "supremeai-memory"],
)
def test_example_config_keeps_registered_servers(sidecar_key):
    """The example config keeps every registered server entry present."""
    config = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    assert sidecar_key in (config.get("mcpServers") or {})
