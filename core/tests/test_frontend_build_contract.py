"""Frontend VITE build-contract automated check (owner P0/P1 hardening queue).

The frontend bakes ``import.meta.env.VITE_*`` values at BUILD time — after deploy they
are immutable, so contract drift here is a production-incident class (silently undefined
API URLs, broken admin routing). This check enforces, with zero frontend build required:

1. **Canonical trio documented** — ``VITE_API_URL`` / ``VITE_USER_BACKEND`` /
   ``VITE_ADMIN_BACKEND`` present with non-placeholder values in the root
   ``.env.example`` (the deploy-time source of truth).
2. **Resolution chain intact** — ``frontend/src/utils/api.ts`` must keep the
   user-portal alias chain (``VITE_USER_BACKEND`` → ``VITE_API_BASE`` →
   ``VITE_API_URL`` → ``VITE_BACKEND_URL``), the admin fallback
   (``VITE_ADMIN_BACKEND`` → user URL), and the production missing-backend guard.
3. **Spec sync** — ``specs/001-dynamic-production-configuration/contracts/config-contract.md``
   still lists the canonical frontend keys.
4. **Declaration baseline** — every ``VITE_`` var referenced in ``frontend/src`` must be
   declared in ``vite-env.d.ts`` OR belong to the locked ``KNOWN_UNDECLARED`` baseline.
   Shrinking the baseline is welcome; adding new undeclared usage fails (silent-undefined
   baking guard).
5. **Type↔build sync** — ``__APP_BUILD_TIME__`` declared in d.ts is defined in
   ``vite.config.ts``.
6. **No dev-password fallback in the frontend bundle source.**
7. **ENV_EVIDENCE_MATRIX.md** records the build-time immutability note for the canonical pair.

Wire-first: read-only checks over owner files — zero owner code modified. The
``KNOWN_UNDECLARED`` baseline documents pre-existing drift for the owner to close
(see PR notes); it may only shrink.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
SRC = FRONTEND / "src"

CANONICAL_TRIO = ("VITE_API_URL", "VITE_USER_BACKEND", "VITE_ADMIN_BACKEND")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read(path: Path) -> str:
    assert path.exists(), f"required contract file missing: {path}"
    return path.read_text(encoding="utf-8")


def _used_vite_vars() -> set[str]:
    """Every import.meta.env.VITE_* identifier referenced in frontend source."""
    used: set[str] = set()
    pattern = re.compile(r"import\.meta\.env\.(VITE_[A-Z0-9_]+)")
    for path in SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        used.update(pattern.findall(path.read_text(encoding="utf-8", errors="replace")))
    return used


def _declared_vite_vars() -> set[str]:
    dts = _read(FRONTEND / "src" / "vite-env.d.ts")
    return set(re.findall(r"readonly\s+(VITE_[A-Z0-9_]+)", dts))


def _env_example_vite_lines() -> dict[str, str]:
    lines: dict[str, str] = {}
    for line in _read(REPO_ROOT / ".env.example").splitlines():
        m = re.match(r"^(VITE_[A-Z0-9_]+)\s*=\s*(.*)$", line.strip())
        if m:
            lines[m.group(1)] = m.group(2).strip()
    return lines


#: Pre-existing drift locked at check introduction (2026-09-15, PR: vite-build-contract).
#: These VITE_ vars are referenced in frontend/src but not declared in vite-env.d.ts —
#: runtime behaviour relies on the `||` fallback chains in utils/api.ts, so they work,
#: but TypeScript autocompletion/typing is blind to them. Owner may close them by adding
#: `readonly <VAR>?: string;` declarations; this set may only SHRINK.
KNOWN_UNDECLARED: frozenset[str] = frozenset()
#: 2026-09-19 (issue #554 / FE-12, PR #658): every previously-undocumented
#: VITE_* read gained an explicit ``vite-env.d.ts`` declaration, so the
#: baseline shrank to empty — the contract's intended end state.


# ---------------------------------------------------------------------------
# 1 — canonical trio documented in .env.example
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("var", CANONICAL_TRIO)
def test_canonical_trio_documented_in_env_example(var: str):
    env = _env_example_vite_lines()
    assert var in env, f"{var} missing from .env.example — deploy-time source of truth"
    value = env[var].split("#")[0].strip()
    assert value, f"{var} present but empty in .env.example"
    assert "your-" not in value or var != "VITE_USER_BACKEND", f"{var} still holds a placeholder"


def test_canonical_trio_values_consistent():
    """The trio in .env.example points at the same backend origin (single-backend doctrine)."""
    env = _env_example_vite_lines()
    values = {v: env[v].split("#")[0].strip() for v in CANONICAL_TRIO}
    assert len(set(values.values())) == 1, f"canonical trio diverges: {values}"


# ---------------------------------------------------------------------------
# 2 — resolution chain + production guard in utils/api.ts
# ---------------------------------------------------------------------------
def test_user_backend_alias_chain_order():
    api_ts = _read(SRC / "utils" / "api.ts")
    chain = re.findall(r"import\.meta\.env\.(VITE_[A-Z0-9_]+)", api_ts)
    user_chain = [
        v
        for v in ("VITE_USER_BACKEND", "VITE_API_BASE", "VITE_API_URL", "VITE_BACKEND_URL")
        if v in chain
    ]
    assert user_chain == [
        "VITE_USER_BACKEND",
        "VITE_API_BASE",
        "VITE_API_URL",
        "VITE_BACKEND_URL",
    ], (
        f"user-portal alias chain drifted: {user_chain} — contract requires "
        "VITE_USER_BACKEND first, legacy aliases as fallbacks"
    )


def test_admin_backend_falls_back_to_user_url():
    api_ts = _read(SRC / "utils" / "api.ts")
    assert re.search(
        r"normalizeBackendUrl\(import\.meta\.env\.VITE_ADMIN_BACKEND\)\s*\|\|\s*USER_BACKEND_URL",
        api_ts,
    ), "admin portal must fall back to the user backend URL when VITE_ADMIN_BACKEND is unset"


def test_production_missing_backend_guard():
    api_ts = _read(SRC / "utils" / "api.ts")
    assert "backendMissing: boolean = import.meta.env.PROD && !USER_BACKEND_URL" in api_ts, (
        "production guard (PROD && !USER_BACKEND_URL) must stay on backendMissing"
    )
    assert "required in production" in api_ts, "operator-facing production error message missing"


# ---------------------------------------------------------------------------
# 3 — spec contract sync
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("var", ("VITE_USER_BACKEND", "VITE_ADMIN_BACKEND"))
def test_config_contract_doc_lists_frontend_keys(var: str):
    doc = _read(
        REPO_ROOT
        / "specs"
        / "001-dynamic-production-configuration"
        / "contracts"
        / "config-contract.md"
    )
    assert f"`{var}`" in doc, f"{var} dropped from the config-contract spec — resync required"


# ---------------------------------------------------------------------------
# 4 — declaration baseline (silent-undefined baking guard)
# ---------------------------------------------------------------------------
def test_every_used_vite_var_is_declared_or_baseline_locked():
    used, declared = _used_vite_vars(), _declared_vite_vars()
    undeclared = used - declared
    novel = undeclared - KNOWN_UNDECLARED
    assert not novel, (
        f"NEW undeclared VITE_ vars referenced in frontend/src without a vite-env.d.ts "
        f"declaration (silent undefined at build time): {sorted(novel)}. Either declare "
        "them in vite-env.d.ts or add to KNOWN_UNDECLARED with owner sign-off."
    )


def test_declaration_baseline_only_shrinks():
    used, declared = _used_vite_vars(), _declared_vite_vars()
    still_undeclared = used - declared
    stale_entries = KNOWN_UNDECLARED - still_undeclared
    assert not stale_entries, (
        f"KNOWN_UNDECLARED contains vars now declared or unused: {sorted(stale_entries)}. "
        "Shrink the baseline — that is the contract improving."
    )


def test_canonical_primary_vars_declared():
    declared = _declared_vite_vars()
    assert "VITE_USER_BACKEND" in declared and "VITE_API_URL" in declared, (
        "primary user-portal vars must stay declared in vite-env.d.ts"
    )


# ---------------------------------------------------------------------------
# 5 — d.ts ↔ vite.config build-time define sync
# ---------------------------------------------------------------------------
def test_app_build_time_defined_in_vite_config():
    dts = _read(FRONTEND / "src" / "vite-env.d.ts")
    config = _read(FRONTEND / "vite.config.ts")
    if "__APP_BUILD_TIME__" in dts:
        assert "__APP_BUILD_TIME__" in config, (
            "__APP_BUILD_TIME__ declared in vite-env.d.ts but not defined in vite.config.ts "
            "— production build would leave the constant undefined"
        )


# ---------------------------------------------------------------------------
# 6 — no dev-password fallback in frontend source
# ---------------------------------------------------------------------------
def test_no_dev_password_only_fallback_in_frontend():
    offenders: list[str] = []
    for path in SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".html"}:
            continue
        if "dev_password_only" in path.read_text(encoding="utf-8", errors="replace"):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"dev_password_only fallback leaked into frontend: {offenders}"


# ---------------------------------------------------------------------------
# 7 — ENV_EVIDENCE_MATRIX.md records build-time immutability for the canonical pair
# ---------------------------------------------------------------------------
def test_manual_steps_documents_vite_build_immutability():
    doc = _read(REPO_ROOT / "docs" / "deployment" / "ENV_EVIDENCE_MATRIX.md")
    assert "VITE_USER_BACKEND" in doc and "VITE_ADMIN_BACKEND" in doc, (
        "ENV_EVIDENCE_MATRIX.md must keep the canonical frontend pair in the env evidence matrix"
    )
    assert "cannot be changed after deployment" in doc, (
        "build-time immutability warning missing from ENV_EVIDENCE_MATRIX.md"
    )
