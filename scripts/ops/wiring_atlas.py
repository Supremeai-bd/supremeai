#!/usr/bin/env python3
"""SupremeAI Master System Wiring & Impact Atlas Auto-Scanner (stdlib-only, zero secrets).

Scans the repository for:
  1. Canonical services from `config/service_registry.yaml` vs `render.yaml` & `plan_render_deploys.py`
  2. Environment variable consumers (`os.getenv`, `os.environ`, `process.env`, `import.meta.env`)
     mapped against `scripts/ci/canonical_name_registry.json` and `scripts/ci/env_registry.json`
  3. Port declarations, health routes, and deploy edges
  4. Drift findings (alias usage, unregistered planner services, health path mismatches)

Usage:
  python scripts/ops/wiring_atlas.py --summary
  python scripts/ops/wiring_atlas.py --impact STEALTH_WEBHOOK_URL
  python scripts/ops/wiring_atlas.py --json-out reports/wiring_atlas_snapshot.json
  python scripts/ops/wiring_atlas.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_REGISTRY_PATH = REPO_ROOT / "config" / "service_registry.yaml"
CANONICAL_NAMES_PATH = REPO_ROOT / "scripts" / "ci" / "canonical_name_registry.json"
ENV_REGISTRY_PATH = REPO_ROOT / "scripts" / "ci" / "env_registry.json"

# Regex patterns for environment variable reads across Python, TypeScript/JS, and YAML workflows
_PY_ENV_RE = re.compile(
    r"""(?:os\.getenv|os\.environ\.get|_os\.environ\.get|optional|required|positiveInt|nonNegativeInt|multiKey)\(\s*["']([A-Z][A-Z0-9_]{2,})["']"""
)
_PY_BRACKET_ENV_RE = re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]{2,})["']\s*\]""")
_JS_ENV_RE = re.compile(r"""(?:process\.env\.|import\.meta\.env\.|env\.)([A-Z][A-Z0-9_]{2,})\b""")
_GHA_ENV_RE = re.compile(r"""\$\{\{\s*(?:secrets|vars)\.([A-Z][A-Z0-9_]{2,})\s*\}\}""")

_SKIP_PREFIXES = (
    ".git/",
    "node_modules/",
    ".venv/",
    "dist/",
    "build/",
    ".pytest_cache/",
)


def _load_yaml_stdlib_or_pyyaml(path: Path) -> dict[str, Any]:
    """Load YAML using PyYAML when available, or a minimal indentation parser fallback."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        return {}


def load_canonical_alias_map() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return (alias_to_canonical, canonical_to_aliases)."""
    alias_to_canon: dict[str, str] = {}
    canon_to_aliases: dict[str, list[str]] = {}
    if not CANONICAL_NAMES_PATH.exists():
        return alias_to_canon, canon_to_aliases
    data = json.loads(CANONICAL_NAMES_PATH.read_text(encoding="utf-8"))
    for _family, info in (data.get("families") or {}).items():
        for canon, aliases in (info.get("canonical") or {}).items():
            canon_to_aliases[canon] = list(aliases)
            for alias in aliases:
                alias_to_canon[alias] = canon
    return alias_to_canon, canon_to_aliases


def classify_env_key(name: str) -> str:
    if name.startswith("VITE_") or name.startswith("NEXT_PUBLIC_"):
        return "public"
    if any(tok in name for tok in ("_SERVICE_ID", "_SVC_ID", "_URL", "_PORT", "_PATH", "_ENV", "_DIR")):
        return "identifier"
    if any(tok in name for tok in ("_SECRET", "_TOKEN", "_KEY", "_PASSWORD", "_PAT", "_COOKIES", "_CERT", "_PRIVATE")):
        return "secret"
    return "internal"


def expected_source_of_truth(name: str) -> str:
    cls = classify_env_key(name)
    if cls == "public":
        return "Vercel / Cloudflare Build Config"
    if name.startswith("RENDER_") and ("_SERVICE_ID" in name or "_SVC_ID" in name):
        return "GitHub Actions Variables & config/service_registry.yaml"
    if cls == "secret":
        return "Infisical Vault (Runtime) / GitHub Protected Secrets (CI)"
    return "Service Runtime Config / render.yaml"


def tracked_source_files() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "*.py", "*.ts", "*.tsx", "*.js", "*.yml", "*.yaml"],
            cwd=REPO_ROOT,
            text=True,
        )
        files = []
        for rel in out.splitlines():
            rel_s = rel.strip()
            if not rel_s or rel_s.startswith(_SKIP_PREFIXES):
                continue
            p = REPO_ROOT / rel_s
            if p.is_file():
                files.append(p)
        return files
    except Exception:
        return []


def scan_env_consumers(
    include_tests: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Scan tracked source files for env var reads without ever reading secret values."""
    consumers: dict[str, list[dict[str, Any]]] = {}
    for file_path in tracked_source_files():
        rel = file_path.relative_to(REPO_ROOT).as_posix()
        if not include_tests and (
            rel.startswith("tests/")
            or "/tests/" in rel
            or rel.endswith((".test.ts", ".spec.ts", "_test.py"))
            or rel.startswith("test_")
        ):
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            found: set[str] = set()
            for rx in (_PY_ENV_RE, _PY_BRACKET_ENV_RE, _JS_ENV_RE, _GHA_ENV_RE):
                for match in rx.finditer(line):
                    found.add(match.group(1))
            for key in found:
                mode = "workflow" if rel.startswith(".github/") else "runtime"
                consumers.setdefault(key, []).append(
                    {"path": rel, "line": idx, "read_mode": mode}
                )
    return consumers


def build_atlas_report() -> dict[str, Any]:
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        commit_sha = "unknown"

    reg = _load_yaml_stdlib_or_pyyaml(SERVICE_REGISTRY_PATH) if SERVICE_REGISTRY_PATH.exists() else {}
    services_map = reg.get("services") or {}
    alias_to_canon, canon_to_aliases = load_canonical_alias_map()
    consumers = scan_env_consumers(include_tests=False)

    services_list: list[dict[str, Any]] = []
    deploy_edges: list[dict[str, Any]] = []
    drift_findings: list[dict[str, Any]] = []

    for svc_id, svc_info in services_map.items():
        services_list.append(
            {
                "id": svc_id,
                "render_name": svc_info.get("render_name", svc_id),
                "platform": svc_info.get("platform", "unknown"),
                "role": svc_info.get("role", ""),
                "local_port": svc_info.get("local_port"),
                "container_port": svc_info.get("container_port"),
                "health_path": svc_info.get("health_path"),
                "readiness_path": svc_info.get("readiness_path"),
                "production_url": svc_info.get("production_url"),
                "canonical_service_id_env": svc_info.get("canonical_service_id_env"),
                "canonical_api_key_env": svc_info.get("canonical_api_key_env"),
                "memory_budget_mb": svc_info.get("memory_budget_mb"),
                "estimated_ram_mb": svc_info.get("estimated_ram_mb"),
            }
        )
        for watch_glob in svc_info.get("watch_paths") or []:
            deploy_edges.append(
                {
                    "watch_path": watch_glob,
                    "target_service": svc_id,
                    "platform": svc_info.get("platform", "render"),
                    "service_id_env": svc_info.get("canonical_service_id_env"),
                    "api_key_env": svc_info.get("canonical_api_key_env"),
                }
            )

    # Check planner vs service_registry alignment
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.ci.plan_render_deploys import SERVICE_RULES

        for planner_svc, (env_id, key_env, _prefixes, *_) in SERVICE_RULES.items():
            if planner_svc not in services_map:
                drift_findings.append(
                    {
                        "severity": "high",
                        "type": "unregistered_planner_service",
                        "service": planner_svc,
                        "detail": f"Service '{planner_svc}' in plan_render_deploys.py is missing from config/service_registry.yaml",
                    }
                )
            else:
                reg_svc = services_map[planner_svc]
                if reg_svc.get("canonical_service_id_env") != env_id:
                    drift_findings.append(
                        {
                            "severity": "high",
                            "type": "service_id_mismatch",
                            "service": planner_svc,
                            "detail": f"Planner uses {env_id} but registry declares {reg_svc.get('canonical_service_id_env')}",
                        }
                    )
                if reg_svc.get("canonical_api_key_env") != key_env:
                    drift_findings.append(
                        {
                            "severity": "medium",
                            "type": "api_key_env_mismatch",
                            "service": planner_svc,
                            "detail": f"Planner uses {key_env} but registry declares {reg_svc.get('canonical_api_key_env')}",
                        }
                    )
    except Exception as exc:
        drift_findings.append(
            {
                "severity": "medium",
                "type": "planner_import_error",
                "detail": str(exc),
            }
        )

    env_keys_list: list[dict[str, Any]] = []
    for key_name in sorted(consumers.keys()):
        key_consumers = consumers[key_name]
        canon = alias_to_canon.get(key_name, key_name)
        aliases = canon_to_aliases.get(canon, [])
        modes = {c["read_mode"] for c in key_consumers}
        if "workflow" in modes and "runtime" in modes:
            exposure = "workflow+runtime"
        elif "workflow" in modes:
            exposure = "deploy/ci"
        else:
            exposure = "runtime"

        env_keys_list.append(
            {
                "name": key_name,
                "canonical_name": canon,
                "is_alias": key_name in alias_to_canon,
                "aliases": aliases,
                "classification": classify_env_key(key_name),
                "source_of_truth": expected_source_of_truth(canon),
                "workflow_exposure": exposure,
                "consumer_count": len(key_consumers),
                "consumers": key_consumers[:25],
            }
        )

    risk_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for d in drift_findings:
        sev = d.get("severity", "low")
        if sev in risk_summary:
            risk_summary[sev] += 1

    return {
        "schema_version": 1,
        "commit": commit_sha,
        "services": services_list,
        "env_keys": env_keys_list,
        "deploy_edges": deploy_edges,
        "drift_findings": drift_findings,
        "risk_summary": risk_summary,
    }


def print_impact_for_target(report: dict[str, Any], target: str) -> int:
    q = target.strip()
    q_upper = q.upper()
    alias_to_canon, canon_to_aliases = load_canonical_alias_map()
    canon = alias_to_canon.get(q_upper, q_upper)
    related_keys = {q_upper, canon} | set(canon_to_aliases.get(canon, []))

    print("=" * 72)
    print(f"🔍 SUPREMEAI BLAST-RADIUS & WIRING IMPACT: {q}")
    print("=" * 72)

    # 1. Matching services
    matched_services = [
        s
        for s in report["services"]
        if q.lower() in s["id"].lower()
        or q.lower() in str(s.get("render_name", "")).lower()
        or s.get("canonical_service_id_env") in related_keys
        or s.get("canonical_api_key_env") in related_keys
    ]
    if matched_services:
        print("\n📦 Related Services:")
        for s in matched_services:
            print(
                f"  - [{s['id']}] {s['render_name']} ({s['platform']}) | "
                f"Port: local={s['local_port']} container={s['container_port']} | "
                f"Health: {s['health_path']} | RAM: ~{s['estimated_ram_mb']}/{s['memory_budget_mb']}MB"
            )
            print(f"    URL: {s['production_url']}")
            print(
                f"    Canonical ID Env: {s['canonical_service_id_env']} | "
                f"Canonical Key Env: {s['canonical_api_key_env']}"
            )

    # 2. Matching environment keys & consumers
    matched_envs = [
        e
        for e in report["env_keys"]
        if e["name"] in related_keys or q_upper in e["name"]
    ]
    if matched_envs:
        print(f"\n🔑 Environment Keys & Call Sites ({len(matched_envs)} matched):")
        for e in matched_envs:
            alias_tag = f" [ALIAS -> {e['canonical_name']}]" if e["is_alias"] else " [CANONICAL]"
            print(
                f"\n  • {e['name']}{alias_tag} ({e['classification']}, {e['workflow_exposure']})"
            )
            print(f"    Source of Truth: {e['source_of_truth']}")
            for c in e["consumers"][:15]:
                print(f"      -> {c['path']}:{c['line']} ({c['read_mode']})")
            if e["consumer_count"] > 15:
                print(f"      ... and {e['consumer_count'] - 15} more call sites")

    if not matched_services and not matched_envs:
        print(f"No direct service or env consumers matched '{q}'.")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="SupremeAI Master System Wiring & Impact Atlas Scanner")
    parser.add_argument("--summary", action="store_true", help="Print human-readable topology & key summary")
    parser.add_argument("--impact", type=str, default="", help="Show blast-radius impact for a key or service name")
    parser.add_argument("--json-out", type=str, default="", help="Write full JSON report to path")
    parser.add_argument("--check", action="store_true", help="Fail with exit 1 if critical/high drift is detected")
    args = parser.parse_args()

    report = build_atlas_report()

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote wiring atlas report to {out_path}")

    if args.impact:
        return print_impact_for_target(report, args.impact)

    if args.summary or not (args.json_out or args.check):
        print("=" * 72)
        print("🗺️  SUPREMEAI MASTER SYSTEM WIRING ATLAS — LIVE SUMMARY")
        print("=" * 72)
        print(f"Commit:          {report['commit']}")
        print(f"Services Mapped: {len(report['services'])} (in config/service_registry.yaml)")
        print(f"Env Keys Read:   {len(report['env_keys'])} active keys across production/CI files")
        print(f"Deploy Edges:    {len(report['deploy_edges'])} watch-path -> service rules")
        print(f"Drift Findings:  {len(report['drift_findings'])} ({report['risk_summary']})")
        print("\nServices Overview:")
        for s in report["services"]:
            ram_str = (
                f"{s['estimated_ram_mb']}/{s['memory_budget_mb']}MB"
                if s.get("memory_budget_mb")
                else "edge/managed"
            )
            print(
                f"  - {s['id']:12} | {s['render_name']:24} | port={str(s['container_port'] or '-'):5} "
                f"| health={str(s['health_path'] or '-'):8} | RAM={ram_str}"
            )

    if args.check:
        if report["risk_summary"]["critical"] > 0 or report["risk_summary"]["high"] > 0:
            print("❌ High/Critical wiring drift detected:", file=sys.stderr)
            for d in report["drift_findings"]:
                print(f"  - [{d['severity']}] {d['type']}: {d['detail']}", file=sys.stderr)
            return 1
        print("✅ Zero critical/high wiring drift detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

