"""The 6-key generator must be safe by construction.

Two failure modes would be expensive here, so both are pinned:

1. **Leaking a secret into the repo.** `--write-policy` must write only public
   metadata (owner / scopes / env / rate_limit) — never the key value, and never
   a secret into `gateway/routing_policy.json`.
2. **Producing a policy the loader rejects.** Generated owners are unique and
   env names distinct, so `parse_routing_policy` must accept the block as-is.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import generate_gateway_keys as gen

from gateway.config import parse_routing_policy


def _keys(count: int = 6, **kwargs):
    return gen.build_keys(count, scopes=kwargs.pop("scopes", ("chat",)), **kwargs)


def test_generates_the_requested_number_of_distinct_keys():
    keys = _keys(6, owner_prefix="client", max_requests=120, window_seconds=None)
    assert len(keys) == 6
    assert len({k["key_id"] for k in keys}) == 6
    assert len({k["secret"] for k in keys}) == 6
    assert len({k["env"] for k in keys}) == 6
    assert [k["owner"] for k in keys] == [f"client-{i}" for i in range(1, 7)]
    assert all(k["rate_limit"] == {"max_requests": 120} for k in keys)


def test_policy_block_never_carries_the_secret():
    keys = _keys(6, owner_prefix="client", max_requests=None, window_seconds=None)
    text = json.dumps(gen.policy_block(keys))
    assert "secret" not in text
    for key in keys:
        assert key["secret"] not in text
        assert key["secret"] not in json.dumps(gen.build_keys(1, scopes=("chat",),
                                                             owner_prefix="other",
                                                             max_requests=None,
                                                             window_seconds=None))


def test_generated_block_is_accepted_by_the_loader():
    keys = _keys(6, owner_prefix="client", max_requests=60, window_seconds=60)
    policy = {
        "schema_version": "gateway-routing/1",
        "chains": {"auto": [{"provider": "groq", "model": "m"}]},
        "default_chain": "auto",
        "rate_limit": {"window_seconds": 60, "max_requests": 100},
        "api_keys": gen.policy_block(keys),
    }
    env = {k["env"]: k["secret"] for k in keys}
    cfg = parse_routing_policy(policy, env=env)
    assert len(cfg.api_keys) == 6
    assert all(record.max_requests == 60 for record in cfg.api_keys.values())


def test_unknown_scope_is_rejected():
    with pytest.raises(ValueError):
        gen.build_keys(1, scopes=("root",), owner_prefix="client",
                       max_requests=None, window_seconds=None)


def test_merge_preserves_other_entries_and_can_replace_by_owner():
    existing = {
        "api_keys": {
            "supremeai-key-existing-00001": {"owner": "pytest", "scopes": ["chat"]},
            "supremeai-key-client-000001": {"owner": "client-1", "scopes": ["chat"]},
        }
    }
    keys = _keys(1, owner_prefix="client", max_requests=None, window_seconds=None)
    merged = gen.merge_policy(existing, keys, replace_owners=False)
    assert "supremeai-key-existing-00001" in merged["api_keys"]
    assert len(merged["api_keys"]) == 3

    merged = gen.merge_policy(existing, keys, replace_owners=True)
    owners = [meta["owner"] for meta in merged["api_keys"].values()]
    assert owners.count("client-1") == 1
    assert "supremeai-key-existing-00001" in merged["api_keys"]


def test_cli_write_policy_never_writes_a_secret(tmp_path, capsys):
    policy_path = tmp_path / "routing_policy.json"
    policy_path.write_text(json.dumps({
        "schema_version": "gateway-routing/1",
        "chains": {"auto": [{"provider": "groq", "model": "m"}]},
        "default_chain": "auto",
        "rate_limit": {"window_seconds": 60, "max_requests": 10},
        "api_keys": {},
    }), encoding="utf-8")

    rc = gen.main(["--count", "6", "--write-policy", "--policy", str(policy_path)])
    assert rc == 0
    written = json.loads(policy_path.read_text(encoding="utf-8"))
    assert len(written["api_keys"]) == 6
    assert "secret" not in policy_path.read_text(encoding="utf-8")
    # Nothing secret reaches stdout either: a terminal is a captured log.
    assert "SUPREMEAI_API_KEY_CLIENT_1=" not in capsys.readouterr().out


def test_secrets_go_to_an_owner_only_file_outside_the_repo(tmp_path):
    secrets_path = tmp_path / "gateway-keys.env"
    assert gen.main(["--count", "3", "--secrets-out", str(secrets_path),
                     "--dry-run"]) == 0
    lines = secrets_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert all(line.startswith("SUPREMEAI_API_KEY_CLIENT_") for line in lines)
    assert secrets_path.stat().st_mode & 0o777 == 0o600


def test_secrets_out_inside_the_repo_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "REPO_ROOT", tmp_path)
    target = tmp_path / "leaked.env"
    assert gen.main(["--count", "1", "--secrets-out", str(target)]) == 2
    assert not target.exists()


def test_existing_secrets_file_is_never_overwritten(tmp_path):
    secrets_path = tmp_path / "gateway-keys.env"
    secrets_path.write_text("KEEP=me\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        gen.main(["--count", "1", "--secrets-out", str(secrets_path)])
    assert secrets_path.read_text(encoding="utf-8") == "KEEP=me\n"


def test_cli_dry_run_writes_nothing(tmp_path):
    policy_path = tmp_path / "routing_policy.json"
    original = json.dumps({"api_keys": {}})
    policy_path.write_text(original, encoding="utf-8")
    assert gen.main(["--count", "3", "--write-policy", "--dry-run",
                     "--policy", str(policy_path)]) == 0
    assert policy_path.read_text(encoding="utf-8") == original
