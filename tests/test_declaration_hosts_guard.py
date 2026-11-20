#!/usr/bin/env python3
"""The hardcoded-host guard must accept declarations but still catch drift.

`mcp.json`, the GitHub App manifest and the A2A agent card are CONSUMER-FACING
declarations: an external client reads the URL out of the file, so the host has
to be written down there. Banning them outright pushed the repo toward blind
file exemptions — and exempting whole files is exactly how the retired
`supremeai-primary-node` host survived in `scripts/ci` for so long.

The rule these tests pin, through `scan_file` (the real entry point): a JSON
line is accepted only when EVERY host on it is already declared by
`config/service_registry.yaml`. A stale host is still a failure, a line mixing
a known host with an unknown one is a failure, and non-JSON code gets no
exemption at all.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = REPO_ROOT / "scripts" / "ci" / "check_hardcoded_deployment_config.py"

TOWER = "https://supremeai-mcp-tower-live.onrender.com/webhooks/github"


def _guard():
    spec = importlib.util.spec_from_file_location("hc_guard_decl", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _scan(tmp_path: Path, name: str, body: str) -> list[str]:
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return _guard().scan_file(target, tmp_path, [])


def test_declared_hosts_are_derived_from_the_registry():
    """No manual list: the set comes from the registry that declares the hosts."""
    declared = _guard().declared_hosts()
    assert declared, "registry declared no hosts — the registry is unreadable"

    import yaml

    registry = yaml.safe_load(
        (REPO_ROOT / "config" / "service_registry.yaml").read_text(encoding="utf-8")
    )
    for spec in registry["services"].values():
        url = spec.get("production_url")
        if url:
            host = url.split("://", 1)[-1].split("/", 1)[0].lower()
            assert host in declared, f"{host} (a registry production_url) is not declared"


def test_json_declaring_a_registry_host_is_accepted(tmp_path):
    assert _scan(tmp_path, "ok.json", '{"url": "%s"}\n' % TOWER) == []


def test_json_declaring_a_retired_host_still_fails(tmp_path):
    """The ghost that motivated this policy must stay caught."""
    body = '{"url": "https://supremeai-primary-node.onrender.com/x"}\n'
    assert _scan(tmp_path, "ghost.json", body) != []


def test_json_declaring_an_unknown_host_still_fails(tmp_path):
    body = '{"url": "https://some-random-studio.vercel.app/x"}\n'
    assert _scan(tmp_path, "unknown.json", body) != []


def test_json_mixing_known_and_stale_hosts_fails(tmp_path):
    """One stale host on the line is enough — no partial credit."""
    body = '{"a": "%s", "b": "https://ghost.onrender.com"}\n' % TOWER
    assert _scan(tmp_path, "mixed.json", body) != []


def test_python_naming_a_registry_host_is_not_exempt(tmp_path):
    """Only data files are declarations; code must resolve hosts from config."""
    assert _scan(tmp_path, "code.py", 'URL = "%s"\n' % TOWER) != []
