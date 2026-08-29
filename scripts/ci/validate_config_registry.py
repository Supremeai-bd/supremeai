#!/usr/bin/env python3
"""Validate SupremeAI's canonical configuration contract without reading secrets.

This is a PR-time structural gate. It deliberately does NOT assert that production
secrets exist (that belongs to deployment/vault validation). It checks that:
  * the canonical registry has unique names and aliases;
  * documented aliases resolve to a canonical key;
  * code/frontend references do not silently introduce new security-sensitive keys;
  * .env.example uses canonical names or documented aliases;
  * legacy aliases are visible as deprecation candidates.

No secret values are printed or loaded.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION = ROOT / "backend" / "core" / "config_classification.py"
ENV_EXAMPLE = ROOT / ".env.example"

# These are intentionally broad enough for Python, JS/TS and config files, but
# only names are extracted; values are never parsed or printed.
ENV_PATTERNS = (
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"os\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]"),
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"import\.meta\.env\.([A-Z][A-Z0-9_]*)"),
)
SECRETISH = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|PRIVATE|CREDENTIAL|AUTH)", re.I)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}
SKIP_FILES = {"secrets_registry.yaml", ".env", ".env.example"}
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml"}


def load_registry():
    import importlib.util

    spec = importlib.util.spec_from_file_location("supremeai_config_classification", CLASSIFICATION)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {CLASSIFICATION}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BY_NAME, module.ALIAS_TO_CANONICAL


def scan_code() -> set[str]:
    found: set[str] = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_EXTS:
            continue
        if path.name in SKIP_FILES or any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in ENV_PATTERNS:
            found.update(pattern.findall(text))
    return found


def env_example_names() -> set[str]:
    if not ENV_EXAMPLE.exists():
        return set()
    names: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            names.add(name)
    return names


def main() -> int:
    by_name, aliases = load_registry()
    all_names = set(by_name) | set(aliases)
    failures: list[str] = []
    warnings: list[str] = []

    # Registry integrity: no alias may point to a missing canonical spec.
    for alias, canonical in sorted(aliases.items()):
        if canonical not in by_name:
            failures.append(f"alias {alias} points to missing canonical key {canonical}")
        if alias in by_name and alias != canonical:
            failures.append(f"alias {alias} is also declared as a canonical key")

    used = scan_code()
    unknown_sensitive = sorted(k for k in used if k not in all_names and SECRETISH.search(k))
    for key in unknown_sensitive:
        warnings.append(f"code uses security-sensitive env key not yet classified: {key}")

    documented = env_example_names()
    for key in sorted(by_name):
        if key not in documented and not any(alias in documented for alias in next((s.aliases for s in by_name.values() if s.name == key), ())):
            # Runtime-only keys are allowed; make this visible rather than failing.
            warnings.append(f"canonical key is absent from .env.example: {key}")

    for alias, canonical in sorted(aliases.items()):
        if alias in documented:
            warnings.append(f"legacy alias present in .env.example: {alias} -> {canonical}")

    print("=== SupremeAI Canonical Configuration Registry ===")
    print(f"canonical keys: {len(by_name)}")
    print(f"aliases: {len(aliases)}")
    print(f"code env references: {len(used)}")
    print(f"security-sensitive unclassified references: {len(unknown_sensitive)}")

    for warning in warnings:
        print(f"::warning::{warning}")
    for failure in failures:
        print(f"::error::{failure}")

    if failures:
        print("❌ FAIL: canonical configuration registry integrity is broken")
        return 1

    print("✅ PASS: canonical registry is structurally valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
