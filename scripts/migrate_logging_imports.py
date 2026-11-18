"""One-shot migration: rewrite `from core.monitoring.logging_config import ...` to
`from core.monitoring.logging_config import ...` across the monorepo.

Idempotent; skips files already migrated.
"""
from pathlib import Path

ROOTS = ["core", "gateway", "scripts", "tests", "backend"]
SKIP = {"__pycache__", ".venv", "node_modules"}
OLD = "core.logging_config"
NEW = "core.monitoring.logging_config"

changed = 0
checked = 0
for root in ROOTS:
    base = Path(root)
    if not base.exists():
        continue
    for py in base.rglob("*.py"):
        if any(part in SKIP for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        if OLD not in text:
            continue
        checked += 1
        new_text = text.replace(
            f"from {OLD} import", f"from {NEW} import"
        ).replace(
            f"import {OLD}", f"import {NEW}"
        )
        if new_text != text:
            py.write_text(new_text, encoding="utf-8")
            changed += 1
            print(f"migrated: {py}")

print(f"\nfiles scanned with old import: {checked}, rewritten: {changed}")
