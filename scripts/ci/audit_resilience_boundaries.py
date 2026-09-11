#!/usr/bin/env python3
"""Report external-service calls that need resilience review.

This is intentionally report-only. It catches missing explicit timeouts at
common HTTP client construction/call sites and records a review queue for
retry/circuit-breaker policy rather than guessing whether a local abstraction
already provides those controls.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

DEFAULT_ROOTS = ("backend",)
EXCLUDED_PARTS = {"tests", "examples", "__pycache__", ".venv", "venv"}
HTTP_CLIENT_NAMES = {"AsyncClient", "Client", "create_async_client", "create_client"}
HTTP_CALL_NAMES = {"get", "post", "put", "patch", "delete", "request", "send"}


def iter_python_files(roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for root_name in roots:
        root = Path(root_name)
        if root.exists():
            files.extend(
                path
                for path in root.rglob("*.py")
                if not EXCLUDED_PARTS.intersection(path.parts)
            )
    return sorted(set(files))


def name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def has_keyword(node: ast.Call, keyword: str) -> bool:
    return any(arg.arg == keyword for arg in node.keywords)


def audit_file(path: Path) -> list[dict[str, object]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [{"file": str(path), "line": 1, "kind": "parse_error", "detail": str(exc)}]

    findings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = name_of(node.func)
        if called in {"AsyncClient", "Client", "create_async_client", "create_client"}:
            if not has_keyword(node, "timeout"):
                findings.append({"file": str(path), "line": node.lineno, "kind": "missing_timeout", "call": called})
            findings.append({"file": str(path), "line": node.lineno, "kind": "policy_review", "call": called, "detail": "Confirm retry and circuit-breaker policy at this boundary."})
        elif called in HTTP_CALL_NAMES and isinstance(node.func, ast.Attribute):
            findings.append({"file": str(path), "line": node.lineno, "kind": "policy_review", "call": called, "detail": "Confirm timeout is inherited and retry/circuit policy is bounded."})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="ci-reports/resilience-boundaries.json")
    parser.add_argument("roots", nargs="*", default=list(DEFAULT_ROOTS))
    args = parser.parse_args()
    findings = [finding for path in iter_python_files(tuple(args.roots)) for finding in audit_file(path)]
    report = {
        "status": "report-only",
        "roots": args.roots,
        "finding_count": len(findings),
        "missing_timeout_count": sum(item["kind"] == "missing_timeout" for item in findings),
        "findings": findings,
        "next_action": "Review each boundary and document bounded timeout, retry, circuit-breaker, and fallback behavior.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Resilience boundary audit: {len(findings)} findings (report-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
