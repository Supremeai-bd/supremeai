#!/usr/bin/env python3
"""
Sync MODULES_LIST.md with Truthful Wiring Audit Results
======================================================
Reads docs/audit_reports/module_wiring_audit.json and updates MODULES_LIST.md
with truthful 5-tier classification and caller/test evidence.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_JSON = ROOT / "docs" / "audit_reports" / "module_wiring_audit.json"
MODULES_LIST = ROOT / "MODULES_LIST.md"

def sync_modules_list():
    with open(AUDIT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    modules = data["modules"]
    counts = data["counts"]
    total = data["total"]

    header = f"""# SupremeAI - Comprehensive List of Modules

Total Modules: **{total}**
**Truthful Operational Wiring Audit Summary (2026-09-11):**
- 🟢 **Operational:** {counts['operational']} modules (Importable + Active Inbound Production Callers > 0 + Test backing)
- 🟡 **Environment-Dependent:** {counts['env_dependent']} modules (Requires host Docker daemon, Telegram bot token, etc.)
- 🟠 **Partially Wired (Dormant):** {counts['partially_wired']} modules (Cleanly importable/standalone; 0 active inbound production callers)
- 🔴 **Broken:** {counts['broken']} modules (Crash on import or missing core dependency)
- ⚪ **Planned:** {counts['planned']} modules (Architectural placeholder)

<!--
ARCHITECTURE DIRECTIVE / GOVERNANCE GUARDRAIL:
Do NOT expand this catalog to file-level granularity (1000+ files).
In SupremeAI architecture, a 'Module' represents a high-level cohesive subsystem, service, monorepo package,
MCP server, tool, or state store. Individual UI components, utility helpers, and type interfaces belong
to their respective parent modules. Preserving the 224 functional module boundary is mandatory for system wiring.
-->

| # | Category | Module Name / Relative Path | Operational Status | Caller Evidence | Test Evidence |
|---|---|---|---|---|---|
"""

    rows = []
    for m in modules:
        mid = m["id"]
        cat = m["category"]
        path = m["path"]
        status = m["status"]
        callers = m.get("callers", [])
        tests = m.get("tests", [])

        caller_str = f"{len(callers)} active callers" if callers else "0 active callers (dormant)"
        if callers and len(callers) <= 2:
            caller_str = ", ".join(callers)
        elif callers:
            caller_str = f"{len(callers)} callers ({callers[0]}, ...)"

        test_str = f"{len(tests)} test files" if tests else "None"
        if tests and len(tests) <= 2:
            test_str = ", ".join(tests)
        elif tests:
            test_str = f"{len(tests)} test files ({tests[0]}, ...)"

        rows.append(f"| {mid} | {cat} | {path} | {status} | {caller_str} | {test_str} |")

    content = header + "\n".join(rows) + "\n"
    with open(MODULES_LIST, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[+] Updated MODULES_LIST.md with truthful operational audit data ({total} rows).")

if __name__ == "__main__":
    sync_modules_list()
