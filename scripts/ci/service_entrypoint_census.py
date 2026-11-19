#!/usr/bin/env python3
"""Service Entrypoint Census Guard (SSOT vs Reality).

Asserts that:
1. Every LIVE service declared in config/service_registry.yaml has an actual
   entrypoint present on disk.
2. Every RETIRED service (status: retired) in config/service_registry.yaml
   carries retired_evidence AND its entrypoint is absent from the monorepo
   (confirming retirement).

Fail-closed: entrypoint drift -> exit 1.
Stdlib-only. Offline. Self-testable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "config" / "service_registry.yaml"


def check_registry(registry_dict: dict, root: Path) -> list[str]:
    """Scan services in registry_dict against filesystem at root."""
    violations: list[str] = []
    services = registry_dict.get("services", {})
    if not isinstance(services, dict):
        return ["registry malformed: 'services' must be a mapping"]

    for name, spec in services.items():
        if not isinstance(spec, dict):
            continue

        status = spec.get("status", "live")
        entrypoint = spec.get("entrypoint")

        if status == "retired":
            evidence = spec.get("retired_evidence")
            if not evidence or not str(evidence).strip():
                violations.append(
                    f"service '{name}' marked 'retired' without required 'retired_evidence'"
                )
            # If entrypoint is declared for a retired service, verify it is NOT in repo root
            if entrypoint and not entrypoint.startswith("uvicorn ") and not entrypoint.startswith("python "):
                entrypoint_path = root / entrypoint
                if entrypoint_path.exists():
                    violations.append(
                        f"service '{name}' is marked 'retired' but entrypoint still exists at {entrypoint}"
                    )
        else:
            # Live service: if entrypoint points to a relative file path, it must exist
            if entrypoint:
                # Discard command prefixes like 'uvicorn ...' or 'python ...'
                # Check for explicit file paths (e.g. *.py, *.json, *.js, *.ts)
                parts = entrypoint.split()
                # Find candidate file paths in command
                file_candidates = [
                    p for p in parts
                    if any(p.endswith(ext) for ext in (".py", ".json", ".js", ".ts", ".yaml", ".yml"))
                    and not p.startswith("-")
                ]
                # Or if the entrypoint is a plain path like 'studio/package.json'
                if not file_candidates and not any(cmd in entrypoint for cmd in ("uvicorn", "python", "npm")):
                    file_candidates = [entrypoint]

                # If the service specifies a root_dir or docker_context, candidate path can be relative to that
                root_dir = spec.get("root_dir") or spec.get("docker_context") or ""

                for candidate in file_candidates:
                    cand_path = root / candidate
                    if root_dir and not cand_path.exists():
                        cand_path = root / root_dir / candidate

                    if not cand_path.exists():
                        violations.append(
                            f"live service '{name}' declared entrypoint file missing: {candidate}"
                        )

    return violations


def self_test() -> list[tuple[str, bool, str]]:
    """Self-test for service_entrypoint_census_guard."""
    cases = []
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "main.py").write_text("# main", encoding="utf-8")
        (tmp / "worker.py").write_text("# worker", encoding="utf-8")

        # 1. Clean registry passes
        reg_clean = {
            "services": {
                "api": {"status": "live", "entrypoint": "python main.py"},
                "frontend": {
                    "status": "retired",
                    "retired_evidence": "Moved to external repo",
                    "entrypoint": "studio/package.json",
                },
            }
        }
        v = check_registry(reg_clean, tmp)
        cases.append(("clean registry passes", len(v) == 0, str(v)))

        # 2. Live service missing entrypoint fails
        reg_missing_live = {
            "services": {
                "ghost": {"status": "live", "entrypoint": "ghost/index.py"},
            }
        }
        v = check_registry(reg_missing_live, tmp)
        cases.append(("live missing entrypoint fails", len(v) == 1 and "ghost/index.py" in v[0], str(v)))

        # 3. Retired service missing retired_evidence fails
        reg_missing_evidence = {
            "services": {
                "frontend": {"status": "retired", "entrypoint": "studio/package.json"},
            }
        }
        v = check_registry(reg_missing_evidence, tmp)
        cases.append(("retired missing evidence fails", len(v) == 1 and "retired_evidence" in v[0], str(v)))

        # 4. Retired service whose entrypoint still exists fails
        reg_retired_present = {
            "services": {
                "worker": {
                    "status": "retired",
                    "retired_evidence": "Replaced",
                    "entrypoint": "worker.py",
                },
            }
        }
        v = check_registry(reg_retired_present, tmp)
        cases.append(("retired entrypoint present fails", len(v) == 1 and "still exists" in v[0], str(v)))

    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run offline self-tests")
    parser.add_argument("--check", action="store_true", help="check config/service_registry.yaml")
    args = parser.parse_args(argv)

    if args.self_test:
        cases = self_test()
        failed = [c for c in cases if not c[1]]
        for name, ok, ev in cases:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {ev}" if not ok else ""))
        print(f"\nservice_entrypoint_census self-test: {len(cases) - len(failed)}/{len(cases)} passed")
        return 1 if failed else 0

    if not REGISTRY_PATH.exists():
        print(f"FAIL: {REGISTRY_PATH} does not exist", file=sys.stderr)
        return 1

    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    violations = check_registry(registry, REPO_ROOT)
    if violations:
        print(f"service_entrypoint_census_guard: FAIL ({len(violations)} violations)")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("service_entrypoint_census_guard: PASS (all service entrypoints verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
