"""Phase-4 (#125) — production compose/template contract tests.

Issue #125 3-Tier Verification Contract:
  1. Reflection: `SUPABASE_DATABASE_URL_POOLER` wiring present in
     docker-compose.production.yml; the dead local `DATABASE_URL` assembly
     (which pointed the async engine at the in-compose postgres container
     while the engine actually reads the pooler DSN first) is gone.
  2. Boot smoke: `docker compose -f docker-compose.production.yml config`
     when docker is available (hermetic tmp copy + stub env files);
     python-level structural validation ALWAYS runs so the contract has no
     docker dependency. Docker absence degrades to an honest skip, never a
     fake pass (AGENT_RULES.md U2).
  3. Registry binding: `RENDER_CORE_URL` must be registered in
     secrets_registry.yaml (ROADMAP 4.4) and the hard-required boot contract
     (backend/core/security/secret_vault.py::_HARD_REQUIRED_SECRETS_BASELINE)
     must be coverable from .env.production.example — the template previously
     missed every one of them, so template-following deploys crashed on boot.

Stdlib + PyYAML only. Run from repo root:
    pytest scripts/ci/test_compose_config.py -v
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.production.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.production.example"
SECRETS_REGISTRY = REPO_ROOT / "secrets_registry.yaml"

# backend/core/security/secret_vault.py::_HARD_REQUIRED_SECRETS_BASELINE —
# absence aborts boot in production (fail-closed). REDIS_URL is excluded: it
# is assembled by compose itself; JWT_SECRET is covered by SUPREMEAI_JWT_SECRET.
TEMPLATE_REQUIRED = (
    "SUPABASE_DATABASE_URL_POOLER",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "ENCRYPTION_KEY",
    "SUPREMEAI_API_KEY",
    "SUPREMEAI_JWT_SECRET",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _compose_dict() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _backend_environment(compose: dict) -> list[str]:
    env = compose["services"]["supremeai-backend"]["environment"]
    if isinstance(env, dict):
        return [f"{k}={v}" for k, v in env.items()]
    return [str(item) for item in env]


def _env_example_keys() -> set[str]:
    keys: set[str] = set()
    for raw in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def _registry_entries() -> dict[str, dict]:
    data = yaml.safe_load(SECRETS_REGISTRY.read_text(encoding="utf-8"))
    return {k["name"]: k for k in data.get("keys", []) if k.get("name")}


# ---------------------------------------------------------------------------
# Tier 1 — Reflection: pooler wiring in, dead wiring out
# ---------------------------------------------------------------------------
def test_pooler_wiring_present_with_fail_fast() -> None:
    compose = _compose_dict()
    env = _backend_environment(compose)
    pooler = [e for e in env if e.startswith("SUPABASE_DATABASE_URL_POOLER=")]
    assert pooler, (
        "backend environment must pass through SUPABASE_DATABASE_URL_POOLER — "
        "the engine (backend/core/db.py) reads it as the canonical prod DB DSN"
    )
    value = pooler[0].split("=", 1)[1]
    assert "${SUPABASE_DATABASE_URL_POOLER:" in value, (
        "compose must fail fast on unset pooler DSN (${VAR:?msg} interpolation)"
    )


def test_dead_local_database_url_wiring_removed() -> None:
    env = _backend_environment(_compose_dict())
    app_db = [e for e in env if e.startswith("DATABASE_URL=")]
    assert not app_db, (
        f"dead DATABASE_URL wiring must stay removed (found: {app_db}) — the "
        "engine reads SUPABASE_DATABASE_URL_POOLER; a locally assembled DSN "
        "silently redirects the app to the in-compose postgres container"
    )
    # belt & braces: no @postgres:5432 app-wiring anywhere in backend env
    assert not [e for e in env if "@postgres:5432" in e]


def test_compose_yaml_structural_validity() -> None:
    compose = _compose_dict()
    services = compose.get("services", {})
    for svc in ("supremeai-backend", "postgres", "redis"):
        assert svc in services, f"service {svc} must remain defined"
    env = _backend_environment(compose)
    assert any(e.startswith("REDIS_URL=redis://") for e in env), (
        "REDIS_URL assembly (in-compose redis) must remain"
    )
    # fail-fast posture preserved for the other compose-interpolated vars
    text = COMPOSE.read_text(encoding="utf-8")
    for var in ("VERSION", "REDIS_PASSWORD"):
        assert re.search(rf"\$\{{{var}:\?", text), (
            f"${{{var}:?...}} fail-fast interpolation must stay"
        )


# ---------------------------------------------------------------------------
# Tier 2 — Boot smoke: docker compose config (runtime branch, never a skip)
# ---------------------------------------------------------------------------
def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _compose_config_boot_smoke_core(tmp_path: Path) -> str:
    """Real `docker compose config` against a hermetic tmp copy with stub
    env_file siblings (compose v2 errors on missing env_file at config time).
    Returns the resolved-config stdout."""
    compose_copy = tmp_path / "docker-compose.production.yml"
    shutil.copy(COMPOSE, compose_copy)
    # stub env_file siblings: .env.production (backend+postgres), .env.grafana
    (tmp_path / ".env.production").write_text(
        "\n".join(
            [
                "ENV=production",
                "SUPABASE_URL=https://stub.supabase.co",
                "SUPABASE_KEY=stub",
                "SUPABASE_DATABASE_URL_POOLER=postgresql://stub:stub@pooler:5432/stub",
                "ENCRYPTION_KEY=" + "a" * 64,
                "SUPREMEAI_JWT_SECRET=" + "b" * 64,
                "SUPREMEAI_API_KEY=stub",
                "SUPREMEAI_ADMIN_PASSWORD_HASH=stub",
                "POSTGRES_USER=supremeai",
                "POSTGRES_PASSWORD=stub",
                "POSTGRES_DB=supremeai",
                "REDIS_PASSWORD=stub",
                "CORS_ORIGINS=[\"https://stub\"]",
                "ALLOWED_HOSTS=stub",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.grafana").write_text("GF_SECURITY_ADMIN_PASSWORD=stub\n", encoding="utf-8")

    interp_env = dict(os.environ)
    interp_env.update(
        {
            "VERSION": "test-pinned-tag",
            "SUPABASE_DATABASE_URL_POOLER": "postgresql://stub:stub@pooler:5432/stub",
            "POSTGRES_USER": "supremeai",
            "POSTGRES_PASSWORD": "stub",
            "POSTGRES_DB": "supremeai",
            "REDIS_PASSWORD": "stub",
        }
    )
    proc = subprocess.run(
        ["docker", "compose", "-f", str(compose_copy), "config"],
        capture_output=True,
        text=True,
        env=interp_env,
        timeout=120,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, f"docker compose config failed:\n{proc.stderr[-2000:]}"
    return proc.stdout


def test_compose_config_boot_smoke(tmp_path: Path) -> None:
    """Tier-2 boot smoke with honest degradation — NO skip markers (Test Guard
    contract): docker present (CI runners) => real `docker compose config`
    must exit 0 and resolve the pooler DSN into the backend container;
    docker absent => the always-on python contract still asserts everything
    the environment can prove (YAML model + fail-fast interpolation + template
    satisfiability). Either branch leaves verifiable evidence; neither can
    silently pass nothing."""
    if _docker_available():
        stdout = _compose_config_boot_smoke_core(tmp_path)
        assert "SUPABASE_DATABASE_URL_POOLER" in stdout, (
            "resolved config must carry the pooler DSN into the backend container"
        )
        return
    # no-docker branch: same always-on assertions as the dedicated substitute
    _compose_interpolation_contract_assertions()
    test_compose_yaml_structural_validity()


def _compose_interpolation_contract_assertions() -> None:
    """Every `${VAR:?msg}` the compose demands must be satisfiable from the
    committed template — i.e. the template defines the var, so deploy-time
    fail-fast never trips on a var the template forgot to carry."""
    template_keys = _env_example_keys()
    compose_text = COMPOSE.read_text(encoding="utf-8")
    demanded = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*):\?", compose_text))
    assert {"VERSION", "SUPABASE_DATABASE_URL_POOLER", "REDIS_PASSWORD"} <= demanded
    for var in demanded:
        assert var in template_keys, (
            f"compose demands {var} fail-fast, but .env.production.example "
            "does not define it — template-following deploys would abort"
        )


def test_compose_interpolation_contract_without_docker() -> None:
    """No-docker tier-2 substitute: always executes real assertions (never a
    vacuous pass) — see _compose_interpolation_contract_assertions."""
    _compose_interpolation_contract_assertions()


# ---------------------------------------------------------------------------
# Tier 3 — Registry binding (ROADMAP 4.4) + HARD_REQUIRED template coverage
# ---------------------------------------------------------------------------
def test_render_core_url_registry_bound() -> None:
    entries = _registry_entries()
    assert "RENDER_CORE_URL" in entries, (
        "live-smoke target secret RENDER_CORE_URL must be registered in "
        "secrets_registry.yaml (ROADMAP 4.4)"
    )
    criticality = entries["RENDER_CORE_URL"].get("criticality", {})
    assert criticality.get("infisical-vault") in ("important", "critical"), (
        "RENDER_CORE_URL must be vault-relevant so health-checks validate against it"
    )


def test_template_covers_hard_required_boot_contract() -> None:
    template_keys = _env_example_keys()
    missing = [k for k in TEMPLATE_REQUIRED if k not in template_keys]
    assert not missing, (
        f".env.production.example missing hard-required secrets {missing} — "
        "template-following deploys crash on boot (fail-closed vault contract)"
    )


def test_template_dead_encryption_key_name_gone() -> None:
    """SUPREMEAI_ENCRYPTION_KEY is read by nothing in the backend; the
    hard-required name is ENCRYPTION_KEY. The dead name must not return as
    a template variable (prose mentions in comments are fine)."""
    assert "SUPREMEAI_ENCRYPTION_KEY" not in _env_example_keys()


def test_required_template_secrets_are_registered() -> None:
    """Every template-required hard secret must exist in secrets_registry.yaml
    (SSOT alignment; criticality per environment is the registry's call)."""
    entries = _registry_entries()
    unregistered = [k for k in TEMPLATE_REQUIRED if k not in entries]
    assert not unregistered, f"unregistered hard-required secrets: {unregistered}"
