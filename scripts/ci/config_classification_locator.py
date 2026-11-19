#!/usr/bin/env python3
"""Locate the canonical configuration-classification source.

`core/config_classification.py` is the metadata SSOT that
`scripts/ci/validate_config_registry.py` and `scripts/ci/check_config_contract.py`
both validate against. Before the monorepo flattening it lived at
`backend/core/config_classification.py`, and both guards kept the old path
hardcoded — so both crashed with `FileNotFoundError` on every run and the only
validators of `config/service_registry.yaml` were effectively dead.

They now share this locator instead of each carrying a copy (a naive fix
duplicated 27 lines and tripped the Zero-New-Code-Clones gate, correctly).

Fail-loud by design: a guard that cannot find its input must not pass.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Newest layout first; the legacy path is kept so an older checkout (or a
# vendored copy) still resolves rather than exploding.
CANDIDATES = (
    REPO_ROOT / "core",
    REPO_ROOT / "backend" / "core",
)
SPEC_FILENAME = "config_classification.py"


def config_dir(root: Path | None = None) -> Path:
    """Return the directory holding `config_classification.py`.

    Raises SystemExit (never a silent skip) when no candidate carries it.
    """
    base = Path(root) if root is not None else REPO_ROOT
    candidates = (
        (base / "core", base / "backend" / "core") if root is not None else CANDIDATES
    )
    for candidate in candidates:
        if (candidate / SPEC_FILENAME).is_file():
            return candidate
    raise SystemExit(
        f"[config-guard] FATAL: {SPEC_FILENAME} not found in "
        f"{', '.join(str(c) for c in candidates)} — refusing to pass without "
        "validating the registry"
    )


def config_spec_path(root: Path | None = None) -> Path:
    return config_dir(root) / SPEC_FILENAME
