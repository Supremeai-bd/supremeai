#!/usr/bin/env python3
"""Service Entrypoint Census Guard (SSOT vs Reality).

`config/service_registry.yaml` is not documentation: keepwarm, deploy planning
and target resolution all read it. When an entry there points at a path that no
longer exists, deploy logic reasons about a service that cannot be built.

Asserted per service:

1. LIVE (`status` absent or `live`): the entrypoint must resolve on disk. Both
   shapes are covered —
     * a file path        `infrastructure/cloudflare-studio-proxy/src/index.js`
     * an ASGI target      `uvicorn gateway.service.app:app` -> gateway/service/app.py
   resolved relative to `docker_context` / `root_dir` when one is declared
   (that is how `scraper`'s `uvicorn main:app` becomes `browser/main.py`).
2. RETIRED (`status: retired`): `retired_evidence` is required, and the
   entrypoint must NOT still exist (a retired surface that reappeared is a
   decision, not a drift to ignore).
3. `status` must be one of `live` / `retired` — a typo must not silently pass
   as "live" and skip the evidence requirement.

Services that declare no entrypoint at all (deploy-time command only) are
reported as unverified, and the PASS line says how many of how many were
actually checked. A guard that prints "all verified" while skipping a third of
the registry is the defect this file exists to prevent.

Fail-closed: drift -> exit 1 · missing PyYAML -> exit 2 (never a traceback).
Stdlib + PyYAML (registry parsing). Offline. Self-testable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the CI preflight
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "config" / "service_registry.yaml"


VALID_STATUSES = {"live", "retired"}
FILE_EXTENSIONS = (".py", ".json", ".js", ".mjs", ".ts", ".tsx", ".yaml", ".yml", ".sh")
_ASGI_TARGET = re.compile(r"\b(?:uvicorn|gunicorn|hypercorn)\s+([A-Za-z0-9_.]+):(\w+)")


def candidate_paths(spec: dict) -> list[str]:
    """Paths a service's entrypoint claims must exist, relative to the repo root.

    Returns [] when the entrypoint carries no path claim (e.g. absent, or a
    bare `npm run start`), so the caller can report it as unverified instead of
    pretending it passed.
    """
    entrypoint = spec.get("entrypoint")
    if not entrypoint or not isinstance(entrypoint, str):
        return []

    candidates: list[str] = []
    asgi = _ASGI_TARGET.search(entrypoint)
    if asgi:
        module = asgi.group(1).replace(".", "/")
        candidates.append(f"{module}.py")
    for token in entrypoint.split():
        if token.startswith("-"):
            continue
        if any(token.endswith(ext) for ext in FILE_EXTENSIONS):
            candidates.append(token)
    if not candidates and not any(
        cmd in entrypoint for cmd in ("uvicorn", "gunicorn", "hypercorn", "python", "npm", "pnpm")
    ):
        candidates.append(entrypoint.strip())

    prefixes = [p for p in (spec.get("root_dir"), spec.get("docker_context")) if p and p != "."]
    resolved: list[str] = []
    for candidate in candidates:
        resolved.append(candidate)
        for prefix in prefixes:
            resolved.append(f"{prefix.rstrip('/')}/{candidate}")
    return resolved


def check_registry(registry_dict: dict, root: Path) -> tuple[list[str], dict]:
    """Return (violations, census) for registry_dict against the tree at root.

    The census is returned so the caller can report coverage honestly:
    {"services": n, "verified": n, "unverified": [names], "retired": [names]}.
    """
    violations: list[str] = []
    census = {"services": 0, "verified": 0, "unverified": [], "retired": []}

    if not isinstance(registry_dict, dict):
        return ["registry malformed: top level must be a mapping"], census
    services = registry_dict.get("services", {})
    if not isinstance(services, dict):
        return ["registry malformed: 'services' must be a mapping"], census

    for name, spec in services.items():
        if not isinstance(spec, dict):
            violations.append(f"service '{name}' is not a mapping")
            continue
        census["services"] += 1

        status = spec.get("status", "live")
        if status not in VALID_STATUSES:
            violations.append(
                f"service '{name}' has unknown status '{status}' — "
                f"allowed: {', '.join(sorted(VALID_STATUSES))} (a typo must not pass as live)"
            )
            continue

        paths = candidate_paths(spec)

        if status == "retired":
            census["retired"].append(name)
            if not str(spec.get("retired_evidence") or "").strip():
                violations.append(
                    f"service '{name}' marked 'retired' without required 'retired_evidence'"
                )
            present = [p for p in paths if (root / p).exists()]
            if present:
                violations.append(
                    f"service '{name}' is marked 'retired' but its entrypoint still exists: "
                    f"{present[0]} (restore it or drop the retirement marker)"
                )
            continue

        if not paths:
            census["unverified"].append(name)
            continue
        if any((root / p).exists() for p in paths):
            census["verified"] += 1
        else:
            violations.append(
                f"live service '{name}' declared entrypoint file missing: {paths[0]}"
            )

    return violations, census


def self_test() -> list[tuple[str, bool, str]]:
    """Hermetic matrix: both entrypoint shapes, both drift directions, typos."""
    import tempfile

    cases: list[tuple[str, bool, str]] = []

    def run(registry: dict, tmp: Path) -> tuple[list[str], dict]:
        return check_registry(registry, tmp)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "main.py").write_text("# main", encoding="utf-8")
        (tmp / "worker.py").write_text("# worker", encoding="utf-8")
        (tmp / "browser").mkdir()
        (tmp / "browser" / "main.py").write_text("# scraper", encoding="utf-8")
        (tmp / "gateway" / "service").mkdir(parents=True)
        (tmp / "gateway" / "service" / "app.py").write_text("# api", encoding="utf-8")

        # 1. Clean registry passes, and coverage is counted honestly.
        violations, census = run(
            {
                "services": {
                    "api": {"entrypoint": "uvicorn gateway.service.app:app --port 8787"},
                    "core": {"entrypoint": "python main.py"},
                    "frontend": {
                        "status": "retired",
                        "retired_evidence": "Moved to external repo",
                        "entrypoint": "studio/package.json",
                    },
                }
            },
            tmp,
        )
        cases.append((
            "clean registry passes (ASGI + file paths)",
            not violations and census["verified"] == 2 and census["retired"] == ["frontend"],
            f"{violations} {census}",
        ))

        # 2. ASGI target whose module does not exist fails — the shape the old
        #    heuristic silently skipped, which left 2 live services unchecked.
        violations, _ = run(
            {"services": {"api": {"entrypoint": "uvicorn gateway.service.gone:app"}}}, tmp
        )
        cases.append((
            "live ASGI entrypoint with missing module fails",
            len(violations) == 1 and "gateway/service/gone.py" in violations[0],
            str(violations),
        ))

        # 3. docker_context prefix is applied (scraper: `uvicorn main:app`).
        violations, census = run(
            {
                "services": {
                    "scraper": {"entrypoint": "uvicorn main:app", "docker_context": "browser"},
                }
            },
            tmp,
        )
        cases.append((
            "docker_context is used to resolve the module",
            not violations and census["verified"] == 1,
            f"{violations} {census}",
        ))

        # 4. A live service with a missing file path fails.
        violations, _ = run({"services": {"ghost": {"entrypoint": "ghost/index.py"}}}, tmp)
        cases.append((
            "live file entrypoint missing fails",
            len(violations) == 1 and "ghost/index.py" in violations[0],
            str(violations),
        ))

        # 5. Retired without evidence fails.
        violations, _ = run(
            {"services": {"frontend": {"status": "retired", "entrypoint": "studio/package.json"}}},
            tmp,
        )
        cases.append((
            "retired without retired_evidence fails",
            len(violations) == 1 and "retired_evidence" in violations[0],
            str(violations),
        ))

        # 6. Retired whose entrypoint came back fails.
        violations, _ = run(
            {"services": {"worker": {"status": "retired", "retired_evidence": "Replaced",
                                     "entrypoint": "worker.py"}}},
            tmp,
        )
        cases.append((
            "retired with a live entrypoint fails",
            len(violations) == 1 and "still exists" in violations[0],
            str(violations),
        ))

        # 7. A status typo must not be treated as live.
        violations, _ = run(
            {"services": {"worker": {"status": "retird", "entrypoint": "worker.py"}}}, tmp
        )
        cases.append((
            "unknown status fails closed",
            len(violations) == 1 and "unknown status" in violations[0],
            str(violations),
        ))

        # 8. A service with no entrypoint is reported as unverified, not as pass.
        violations, census = run({"services": {"ci-runner": {"platform": "render"}}}, tmp)
        cases.append((
            "entrypoint-less service is unverified, not verified",
            not violations and census["unverified"] == ["ci-runner"],
            f"{violations} {census}",
        ))

    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run the offline matrix")
    parser.add_argument("--check", action="store_true", help="check config/service_registry.yaml")
    args = parser.parse_args(argv)

    if args.self_test:
        cases = self_test()
        failed = [c for c in cases if not c[1]]
        for name, ok, evidence in cases:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {evidence}" if not ok else ""))
        print(f"\nservice_entrypoint_census self-test: {len(cases) - len(failed)}/{len(cases)} passed")
        return 1 if failed else 0

    if yaml is None:
        print("PyYAML required: pip install pyyaml", file=sys.stderr)
        return 2
    if not REGISTRY_PATH.exists():
        print(f"FAIL: {REGISTRY_PATH} does not exist", file=sys.stderr)
        return 1

    try:
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # fail-closed, never guess around an unreadable SSOT
        print(f"FAIL: {REGISTRY_PATH} is not valid YAML: {exc}", file=sys.stderr)
        return 1

    violations, census = check_registry(registry, REPO_ROOT)
    unverified = ", ".join(census["unverified"]) or "none"
    retired = ", ".join(census["retired"]) or "none"
    coverage = (
        f"verified {census['verified']}/{census['services']} service entrypoints "
        f"· no entrypoint declared: {unverified} · retired: {retired}"
    )
    if violations:
        print(f"service_entrypoint_census_guard: FAIL ({len(violations)} violation(s))")
        for violation in violations:
            print(f"  - {violation}")
        print(f"  census: {coverage}")
        return 1

    print(f"service_entrypoint_census_guard: PASS ({coverage})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
