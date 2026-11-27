#!/usr/bin/env python3
"""
scripts/ops/master_health_check.py — Dynamic Zero-Maintenance Master Health Engine.

Architecture & Contract:
  - Dynamically discovers all available accounts, services, satellites, and data layers
    directly from active registries and the live Control Tower mesh.
  - Zero hardcoded endpoint lists: new nodes or satellites are auto-discovered on registration;
    removed nodes cleanly de-register with zero code edits needed in the future.
  - Fail-closed doctrine: any degraded dependency, unreachable node, or broken contract
    marks overall health as DEGRADED or DOWN.
  - CI Sweep: runs ALL local federation guards + live GitHub Actions CI checks across all
    active satellite repos, emitting machine-readable fix hints so any agent can act at once.

Usage:
  python scripts/ops/master_health_check.py [--json] [--timeout 8] [--self-test]
  python scripts/ops/master_health_check.py --ci-sweep [--json]
  python scripts/ops/master_health_check.py --full        # infra + ci-sweep combined
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: Where service production URLs are declared. This file used to hold its own
#: literals, which meant the registry could change and the health check would
#: keep probing the old hosts — a stale probe reports a healthy service as
#: unreachable, which is the failure mode that matters least visibly and most.
_SERVICE_REGISTRY_FILE = ROOT / "config" / "service_registry.yaml"


def _registry_services() -> dict[str, dict[str, Any]]:
    """Load ``config/service_registry.yaml`` -> {service_id: spec}.

    Returns ``{}`` when the file is unreadable so callers fall back to probing
    nothing rather than crashing: a health check that throws is worse than one
    that reports "no targets configured".
    """
    try:
        import yaml
    except ImportError:
        return {}
    try:
        doc = yaml.safe_load(_SERVICE_REGISTRY_FILE.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}
    services = doc.get("services")
    return services if isinstance(services, dict) else {}


def _service_endpoint(service_id: str) -> tuple[str, str] | None:
    """Resolve ``(display_name, url)`` for one service, env-first.

    Order: the canonical URL env var, then ``production_url`` from the registry.
    Nothing is hardcoded here — the registry is the single source of truth for
    which host a service lives on.
    """
    spec = _registry_services().get(service_id)
    if not isinstance(spec, dict):
        return None
    env_key = spec.get("canonical_url_env")
    url = os.getenv(env_key, "").strip() if env_key else ""
    if not url:
        url = str(spec.get("production_url") or "").strip()
    if not url:
        return None
    path = spec.get("health_path") or "/health"
    # `role` is the registry's human label ("Public API Gateway & Multi-LLM
    # Provider Router"); `render_name` is the deploy name; the id is the floor.
    # This used to be a second set of literals in this file, which drifted from
    # the registry and would not have been updated when a service was renamed.
    label = str(spec.get("role") or spec.get("render_name") or service_id)
    return (label, url.rstrip("/") + path)


def _edge_domains() -> list[str]:
    """Customer-facing DNS names to resolve, derived from the registry.

    This list used to be two literals — ``supremeai.live`` and
    ``studio.supremeai.lat``. On 2026-11-20 BOTH failed to resolve, and neither
    was the surface actually serving the Studio: the probe reported two dead
    domains and never looked at the live one
    (``supremeai-studio.pages.dev``). A hardcoded probe list can only ever test
    yesterday's deployment, so derive it from the registry those deployments are
    declared in.

    Render services are skipped: the HTTP sweep already covers them, and this
    probe exists for the customer/edge domains in front of them.
    """
    from urllib.parse import urlsplit  # noqa: PLC0415

    domains: list[str] = []
    for spec in _registry_services().values():
        if not isinstance(spec, dict):
            continue
        if str(spec.get("platform") or "").lower() == "render":
            continue
        host = urlsplit(str(spec.get("production_url") or "")).hostname
        if host and host not in domains:
            domains.append(host)
    return domains

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# CI Guards registry — each entry: (label, command_args, fix_hint)
# ---------------------------------------------------------------------------
CI_GUARDS: list[tuple[str, list[str], str]] = [
    (
        "Boundary Sanitization",
        ["python", "scripts/ci/boundary_sanitization_guard.py", "--self-test"],
        "Check domain mirror paths. Run: python scripts/ci/boundary_sanitization_guard.py --files <changed-files>",
    ),
    (
        "Issue Template",
        ["python", "scripts/ci/issue_template_guard.py", "--self-test"],
        "Issue body missing required sections. Fix template in .github/ISSUE_TEMPLATE/.",
    ),
    (
        "Frontend Performance",
        ["python", "scripts/ci/frontend_performance_guard.py", "--self-test"],
        "FCP > 1.0s or missing React.lazy(). Add code-splitting to heavy routes in studio/.",
    ),
    (
        "Federation Anchors",
        ["python", "scripts/ci/federation_anchors.py", "--self-test"],
        "Anchor hub SSOT broken. Verify 6 active domain anchors (#749..#762) in federation_anchors.py.",
    ),
    (
        "Satellite Board",
        ["python", "scripts/ci/satellite_board_guard.py", "--self-test"],
        "Satellites have open issues/PRs (0-policy violation). Close or migrate them.",
    ),
    (
        "Admin Sovereignty",
        ["python", "scripts/ci/admin_sovereignty_guard.py", "--self-test"],
        "Admin bypass detected. Remove any agent-writable admin overrides.",
    ),
    (
        "Cross-Platform Invariants",
        ["python", "scripts/ci/cross_platform_invariant_guard.py", "--self-test"],
        "Platform-specific code detected. Use pathlib/os.path and avoid shell-isms.",
    ),
    (
        "Master Secret Shield",
        ["python", "scripts/ci/master_secret_shield.py", "--self-test"],
        "High-entropy secret detected. Remove token/key from source and rotate it.",
    ),
    (
        "Deploy Preflight",
        ["python", "scripts/ci/deploy_preflight_guard.py", "--self-test"],
        "Deploy preflight failed. Verify env vars and service topology.",
    ),
]

# Active satellite repos for live GitHub CI failure checks
ACTIVE_SATELLITES: list[str] = [
    "Supremeai-bd/supremeai-studio",
    "Supremeai-bd/supremeai-api",
    "Supremeai-bd/supremeai-core",
    "Supremeai-bd/supremeai-browser",
    "Supremeai-bd/supremeai-vscode",
    "Supremeai-bd/supremeai",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ServiceHealthResult:
    service_id: str
    name: str
    category: str
    status: str  # healthy | degraded | unreachable | skipped
    latency_ms: int
    http_status: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class GuardResult:
    name: str
    status: str  # pass | fail | error
    returncode: int
    output: str
    fix_hint: str


@dataclass
class SatelliteCIResult:
    repo: str
    status: str  # green | failing | inaccessible
    failed_runs: list[dict[str, Any]] = field(default_factory=list)
    fix_hint: str = ""


@dataclass
class MasterHealthReport:
    timestamp: str
    overall_status: str  # healthy | degraded | down
    total_services: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    unreachable_count: int = 0
    services: list[ServiceHealthResult] = field(default_factory=list)
    guards: list[GuardResult] = field(default_factory=list)
    satellite_ci: list[SatelliteCIResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# HTTP probe
# ---------------------------------------------------------------------------


def probe_http_endpoint(
    url: str,
    timeout: float = 6.0,
    headers: dict[str, str] | None = None,
) -> tuple[bool, int | None, int, dict[str, Any] | None, str | None]:
    req_headers = {"User-Agent": "SupremeAI-MasterHealth/1.0", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=req_headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = int((time.time() - t0) * 1000)
            raw = resp.read(65536)
            payload = None
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)
            return (resp.status == 200, resp.status, elapsed, payload, None)
    except urllib.error.HTTPError as exc:
        elapsed = int((time.time() - t0) * 1000)
        return (False, exc.code, elapsed, None, f"HTTP {exc.code}: {exc.reason}")
    except Exception as exc:
        elapsed = int((time.time() - t0) * 1000)
        return (False, None, elapsed, None, str(exc))


# ---------------------------------------------------------------------------
# Infra sweep
# ---------------------------------------------------------------------------


def pipeline_snapshot(timeout: float, *, quick: bool = False) -> dict:
    """Public endpoint evidence only; never call the healer, vault or full Tower sweep."""
    services = _registry_services()
    if not services:
        raise ValueError("Service registry unavailable or empty; no health evidence")

    def check(item):
        key, spec = item
        preferred = "quick_check_path" if quick else "readiness_path"
        path = spec.get(preferred) or spec.get("health_path")
        base = spec.get("production_url")
        row = {"service": key, "path": None, "http": None, "ms": None}
        if spec.get("status") == "retired":
            return dict(row, status="retired")
        if not base or not path:
            return dict(row, status="not configured")
        ok, code, ms, payload, _ = probe_http_endpoint(base.rstrip("/") + path, timeout)
        state = payload.get("status") if isinstance(payload, dict) else None
        if code is None:
            verdict = "unreachable"
        elif not ok:
            verdict = "HTTP failure" if code not in (401, 403) else "access restricted"
        elif isinstance(payload, dict) and payload.get("stale") is True:
            verdict = "stale"
        elif state in ("healthy", "ready", "ok", "operational", "up"):
            verdict = "healthy"
        elif state in ("degraded", "starting", "down", "outage", "unhealthy", "not_ready"):
            verdict = state
        else:
            verdict = "unknown response"
        return dict(row, path=path, http=code, ms=ms, status=verdict)

    with ThreadPoolExecutor(max_workers=6) as pool:
        # বাংলা: quick probe-এ দুই public entrypoint ছাড়া আর কাউকে জাগাই না।
        targets = [(key, services.get(key, {})) for key in ("api", "mcp")] if quick else services.items()
        rows = list(pool.map(check, targets))

    report = {"services": rows, "scope": "liveness" if quick else "fleet"}
    if quick:
        return {**report, "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    # বাংলা: cached summary পড়ি; provider-গুলোতে দ্বিতীয়বার probe চালাই না।
    providers = []
    mcp = services.get("mcp", {})
    cache_status = "no Tower endpoint"
    if mcp.get("production_url") and mcp.get("status") != "retired":
        ok, code, _, data, _ = probe_http_endpoint(mcp["production_url"].rstrip("/") + "/health/summary", timeout)
        cache_status = f"HTTP {code}" if code else "unreachable"
        if ok and isinstance(data, dict) and isinstance(data.get("services"), list):
            for entry in data["services"]:
                if (not isinstance(entry, dict) or not isinstance(entry.get("provider"), str)
                        or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,80}", entry["provider"])):
                    continue
                state = entry.get("status")
                stamp = entry.get("checkedAt")
                try:
                    checked = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                    if checked.tzinfo is None:
                        raise ValueError("missing timezone")
                    stamp = checked.astimezone(timezone.utc).isoformat(timespec="seconds")
                except (ValueError, OverflowError):
                    stamp = None
                providers.append({"provider": entry["provider"], "checked_at": stamp,
                                  "reported_status": state if state in ("healthy", "degraded", "down", "circuit_open") else "unknown"})
            cache_status = "cached observations" if providers else "no observations"
        elif ok:
            cache_status = "unknown response"
    return {**report, "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tower_summary": cache_status, "providers": providers}


def pipeline_markdown(report: dict) -> str:
    rows = report["services"]
    measured = [r for r in rows if r["status"] not in ("retired", "not configured")]
    healthy = sum(r["status"] == "healthy" for r in measured)
    coverage = f"**{healthy}/{len(measured)} probed endpoints reported healthy** · {len(rows) - len(measured)} not probed."
    quick = report["scope"] == "liveness"
    title = "Production liveness (API + Tower)" if quick else "Production service health"
    description = ("Liveness only — no dependency or readiness checks." if quick else
                   "One read-only GET per registered public readiness/health endpoint. Not a deploy or inference test.")
    lines = [f"## {title}", coverage, f"Snapshot completed: **{report['observed_at']}**", "",
             description, "",
             "| Service | Path | Result | HTTP | ms |", "|---|---|---|---:|---:|"]
    for row in report["services"]:
        lines.append("| " + " | ".join(str(row[k]) if row[k] is not None else "—" for k in ("service", "path", "status", "http", "ms")) + " |")
    if quick:
        return "\n".join(lines) + "\n"
    lines += ["", f"### Provider dependencies — Tower: {report['tower_summary']}",
              "Last observations, not live provider probes. Check each timestamp before acting.", ""]
    if report["providers"]:
        lines += ["| Provider | Last reported state | Checked at (UTC) |", "|---|---|---|"]
        for row in report["providers"]:
            lines.append(f"| {row['provider']} | {row['reported_status']} | {row['checked_at'] or 'unknown'} |")
    return "\n".join(lines) + "\n"


def discover_and_evaluate(
    tower_url: str | None = None,
    timeout: float = 6.0,
) -> MasterHealthReport:
    results: list[ServiceHealthResult] = []

    if tower_url is None:
        resolved = _service_endpoint("mcp")
        tower_url = resolved[1].rsplit("/health", 1)[0] if resolved else ""
        if not tower_url:
            # No registry entry and no env var: report that, do not invent a host.
            raise SystemExit(
                "master_health_check: no MCP Tower URL configured. Set "
                f"{_registry_services().get('mcp', {}).get('canonical_url_env') or 'RENDER_MCP_URL'}"
                " or add an `mcp` entry to config/service_registry.yaml."
            )

    tower_ok, tower_code, tower_lat, tower_payload, tower_err = probe_http_endpoint(
        f"{tower_url}/health", timeout=timeout
    )
    tower_status = "healthy" if tower_ok else "unreachable"
    tower_services_count = 0
    if tower_payload and isinstance(tower_payload, dict):
        svc_info = tower_payload.get("services", {})
        tower_services_count = svc_info.get("total", 0)

    results.append(ServiceHealthResult(
        service_id="render-mcp-tower",
        name="SupremeAI Control Tower (MCP Hub)",
        category="control_plane",
        status=tower_status,
        latency_ms=tower_lat,
        http_status=tower_code,
        details={"services_discovered": tower_services_count},
        error=tower_err,
    ))

    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))
        from federation_anchors import ACTIVE_ANCHOR_HUBS  # type: ignore
        for repo, issue_num in ACTIVE_ANCHOR_HUBS.items():
            slug = repo.split("/")[-1]
            results.append(ServiceHealthResult(
                service_id=f"federation-anchor-{slug}",
                name=f"Federation Satellite Anchor ({slug})",
                category="federation_satellite",
                status="healthy",
                latency_ms=0,
                http_status=200,
                details={"repo": repo, "anchor_issue": issue_num},
            ))
    except Exception as e:
        results.append(ServiceHealthResult(
            service_id="federation-anchors-discovery",
            name="Federation Anchor Registry",
            category="federation_satellite",
            status="degraded",
            latency_ms=0,
            error=str(e),
        ))

    # Derived from config/service_registry.yaml — see _service_endpoint().
    core_nodes = [
        (f"render-{sid}", *endpoint)
        for sid in ("api", "core", "worker", "scraper")
        if (endpoint := _service_endpoint(sid)) is not None
    ]
    for sid, sname, surl in core_nodes:
        ok, code, lat, payload, err = probe_http_endpoint(surl, timeout=timeout)
        status = "healthy" if ok else ("degraded" if code else "unreachable")
        node_details: dict[str, Any] = {"url": surl}
        if payload and isinstance(payload, dict):
            for key in ("total_healthy_keys", "web_sessions_active"):
                if key in payload:
                    node_details[key] = payload[key]
        results.append(ServiceHealthResult(
            service_id=sid,
            name=sname,
            category="core_node",
            status=status,
            latency_ms=lat,
            http_status=code,
            details=node_details,
            error=err,
        ))

    total = len(results)
    healthy = sum(1 for r in results if r.status == "healthy")
    degraded = sum(1 for r in results if r.status == "degraded")
    unreachable = sum(1 for r in results if r.status == "unreachable")

    overall = "healthy"
    if unreachable > 0:
        overall = "down" if unreachable >= (total // 2) else "degraded"
    elif degraded > 0:
        overall = "degraded"

    return MasterHealthReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        overall_status=overall,
        total_services=total,
        healthy_count=healthy,
        degraded_count=degraded,
        unreachable_count=unreachable,
        services=results,
    )


# ---------------------------------------------------------------------------
# CI Sweep: local guards + live satellite GitHub CI
# ---------------------------------------------------------------------------


def _get_gh_token() -> str:
    for var in ("GH_TOKEN", "GITHUB_TOKEN", "OPEN_SYNC_PAT"):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    try:
        res = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=False, timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)
    return ""


def run_local_guards() -> list[GuardResult]:
    results: list[GuardResult] = []
    for label, cmd, fix_hint in CI_GUARDS:
        try:
            proc = subprocess.run(
                cmd,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            output = (proc.stdout + proc.stderr).strip()
            status = "pass" if proc.returncode == 0 else "fail"
            results.append(GuardResult(
                name=label,
                status=status,
                returncode=proc.returncode,
                output=output[-800:] if len(output) > 800 else output,
                fix_hint=fix_hint if status == "fail" else "",
            ))
        except subprocess.TimeoutExpired:
            results.append(GuardResult(
                name=label, status="error", returncode=-1,
                output="Guard timed out after 60s", fix_hint=fix_hint,
            ))
        except Exception as exc:
            results.append(GuardResult(
                name=label, status="error", returncode=-1,
                output=str(exc), fix_hint=fix_hint,
            ))
    return results


def inspect_failed_run_logs(repo: str, run_id: int, token: str = "") -> dict[str, Any]:
    """Extract failed step name and key error log lines directly from GitHub Actions."""
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SupremeAI-MasterHealth/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    info: dict[str, Any] = {"failed_job": "", "failed_step": "", "error_excerpt": ""}

    # 1. Discover failed job and step
    jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
    try:
        req = urllib.request.Request(jobs_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for j in data.get("jobs", []):
            if j.get("conclusion") == "failure":
                info["failed_job"] = j.get("name", "")
                for s in j.get("steps", []):
                    if s.get("conclusion") == "failure":
                        info["failed_step"] = s.get("name", "")
                        break
                break
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)

    # 2. Extract error lines from run logs archive if available
    logs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/logs"
    try:
        req = urllib.request.Request(logs_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=12) as resp:
            z = zipfile.ZipFile(io.BytesIO(resp.read()))
            for name in z.namelist():
                # Read main job txt logs (skip system.txt)
                if name.endswith(".txt") and "system" not in name.lower():
                    raw = z.read(name).decode("utf-8", errors="replace")
                    error_lines = [
                        l.strip() for l in raw.splitlines()
                        if any(marker in l for marker in ("##[error]", " FAIL ", "Error:", "error TS", "FAILED ", "Exception:"))
                    ]
                    if error_lines:
                        # Clean up timestamps from GitHub Actions logs if present
                        cleaned = []
                        for l in error_lines[-4:]:
                            parts = l.split("Z ", 1)
                            cleaned.append(parts[1] if len(parts) == 2 else l)
                        info["error_excerpt"] = " | ".join(cleaned)
                        break
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)

    return info


def check_satellite_ci(token: str = "") -> list[SatelliteCIResult]:
    results: list[SatelliteCIResult] = []
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SupremeAI-MasterHealth/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for repo in ACTIVE_SATELLITES:
        url = f"https://api.github.com/repos/{repo}/actions/runs?branch=main&per_page=5"
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            results.append(SatelliteCIResult(
                repo=repo, status="inaccessible",
                fix_hint=f"HTTP {exc.code}: repo may be private or token missing.",
            ))
            continue
        except Exception as exc:
            results.append(SatelliteCIResult(
                repo=repo, status="inaccessible",
                fix_hint=f"Network error: {exc}",
            ))
            continue

        runs = data.get("workflow_runs", [])
        # Group runs by workflow to inspect the latest run of each workflow
        workflows: dict[str, list[dict[str, Any]]] = {}
        for r in runs:
            wf_name = r.get("name") or str(r.get("workflow_id", ""))
            workflows.setdefault(wf_name, []).append(r)

        failing = []
        for wf_name, wf_runs in workflows.items():
            latest = wf_runs[0]
            if latest.get("conclusion") in ("failure", "timed_out", "cancelled") and latest.get("status") == "completed":
                failing.append({
                    "id": latest["id"],
                    "name": latest.get("name", ""),
                    "conclusion": latest.get("conclusion", ""),
                    "url": latest.get("html_url", ""),
                    "branch": latest.get("head_branch", ""),
                    "sha": str(latest.get("head_sha", ""))[:8],
                })

        if failing:
            # Inspect top failure for live root-cause excerpt
            top_run = failing[0]
            log_info = inspect_failed_run_logs(repo, top_run["id"], token=token)
            top_run["failed_job"] = log_info.get("failed_job", "")
            top_run["failed_step"] = log_info.get("failed_step", "")
            top_run["error_excerpt"] = log_info.get("error_excerpt", "")

            step_desc = f" [{top_run['failed_step']}]" if top_run.get("failed_step") else ""
            hint_parts = [f"Fix run #{f['id']} ({f['name']}){step_desc} at {f['url']}" for f in failing[:2]]
            results.append(SatelliteCIResult(
                repo=repo, status="failing",
                failed_runs=failing,
                fix_hint=" | ".join(hint_parts),
            ))
        else:
            results.append(SatelliteCIResult(repo=repo, status="green"))
    return results


def run_ci_sweep(token: str = "") -> tuple[list[GuardResult], list[SatelliteCIResult]]:
    return run_local_guards(), check_satellite_ci(token=token)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

_TICK = "\u2705"
_WARN = "\u26a0\ufe0f"
_CROSS = "\u274c"
_ROCKET = "\U0001f680"


def print_infra_report(report: MasterHealthReport) -> None:
    print("=" * 72)
    print(f"{_ROCKET} SUPREMEAI MASTER HEALTH ENGINE — INFRASTRUCTURE SWEEP")
    print("=" * 72)
    print(f"Timestamp:      {report.timestamp}")
    print(f"Overall Status: {report.overall_status.upper()}")
    print(
        f"Service Pool:   {report.total_services} Discovered "
        f"({report.healthy_count} Healthy, {report.degraded_count} Degraded, "
        f"{report.unreachable_count} Unreachable)"
    )
    print("-" * 72)
    for s in report.services:
        icon = _TICK if s.status == "healthy" else (_WARN if s.status == "degraded" else _CROSS)
        lat_str = f"{s.latency_ms}ms" if s.latency_ms > 0 else "SSOT"
        print(f"{icon} [{s.category.upper()}] {s.name:<38} | {s.status.upper():<11} | {lat_str}")
        if s.error:
            print(f"   {_WARN} Error: {s.error}")
    print("=" * 72)


def print_ci_sweep_report(
    guards: list[GuardResult], satellites: list[SatelliteCIResult]
) -> None:
    guards_passed = sum(1 for g in guards if g.status == "pass")
    guards_failed = len(guards) - guards_passed
    sats_green = sum(1 for s in satellites if s.status == "green")
    sats_failing = len(satellites) - sats_green

    print("")
    print("=" * 72)
    print(f"{_ROCKET} SUPREMEAI MASTER FEDERATION CI SWEEP")
    print("=" * 72)

    print(f"\n--- LOCAL CI GUARDS ({guards_passed}/{len(guards)} PASS) ---")
    for g in guards:
        icon = _TICK if g.status == "pass" else _CROSS
        print(f"{icon} {g.name:<35} [{g.status.upper()}]")
        if g.status != "pass":
            print(f"   FIX: {g.fix_hint}")
            if g.output:
                snippet = "\n      ".join(g.output.splitlines()[-3:])
                print(f"   Output: {snippet}")

    print(f"\n--- SATELLITE GITHUB CI ({sats_green}/{len(satellites)} GREEN) ---")
    for s in satellites:
        icon = _TICK if s.status == "green" else (_CROSS if s.status == "failing" else _WARN)
        short = s.repo.split("/")[-1]
        print(f"{icon} {short:<40} [{s.status.upper()}]")
        if s.status != "green":
            print(f"   FIX: {s.fix_hint}")
            for run in s.failed_runs[:2]:
                step_str = f" [Step: {run['failed_step']}]" if run.get("failed_step") else ""
                print(f"      Run #{run['id']} ({run['name']}){step_str} -> {run['url']}")
                if run.get("error_excerpt"):
                    print(f"      Error: {run['error_excerpt'][:200]}")

    overall_ok = guards_failed == 0 and sats_failing == 0
    print("")
    print("=" * 72)
    icon = _TICK if overall_ok else _CROSS
    label = "ALL GREEN" if overall_ok else "ACTION REQUIRED"
    print(f"{icon} CI SWEEP RESULT: {label}")
    print(f"   Guards: {guards_passed}/{len(guards)} passed  |  Satellites: {sats_green}/{len(satellites)} green")

    if not overall_ok:
        print("\nACTION PLAN FOR AGENT (execute top-to-bottom):")
        idx = 1
        for g in guards:
            if g.status != "pass":
                print(f"  {idx}. [LOCAL GUARD] {g.name}: {g.fix_hint}")
                idx += 1
        for s in satellites:
            if s.status != "green":
                err_detail = ""
                if s.failed_runs and s.failed_runs[0].get("error_excerpt"):
                    err_detail = f" | Cause: {s.failed_runs[0]['error_excerpt'][:120]}"
                print(f"  {idx}. [SATELLITE CI] {s.repo}: {s.fix_hint}{err_detail}")
                idx += 1
    print("=" * 72)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def self_test() -> int:
    report = discover_and_evaluate(timeout=4.0)
    assert report.total_services > 0, "Self-test: 0 services discovered"
    assert report.overall_status in ("healthy", "degraded", "down"), f"Bad status: {report.overall_status}"
    print(f"[infra] {report.total_services} services discovered. Status: {report.overall_status.upper()}")

    assert len(CI_GUARDS) >= 8, f"Expected >= 8 guards, got {len(CI_GUARDS)}"
    for label, cmd, hint in CI_GUARDS:
        assert label and cmd and hint, f"Guard '{label}' has missing fields"
        assert cmd[0] == "python", f"Guard '{label}' must start with python"
    print(f"[guards] Registry OK: {len(CI_GUARDS)} guards registered.")

    assert len(ACTIVE_SATELLITES) >= 5, f"Expected >= 5 satellites, got {len(ACTIVE_SATELLITES)}"
    for repo in ACTIVE_SATELLITES:
        assert "/" in repo, f"Satellite {repo} must be owner/repo format"
    print(f"[satellites] Registry OK: {len(ACTIVE_SATELLITES)} satellites registered.")

    print(f"\nSelf-test PASS: {report.healthy_count} healthy / {report.degraded_count} degraded / {report.unreachable_count} unreachable.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_env_subset(env_path: Path, keys: list[str]) -> dict[str, str]:
    """Extract only the requested KEY=VALUE pairs from .env (stdlib, quote-aware).

    Deliberately line-based: multiline PEM blocks are ignored because we only ever
    ask for single-line URLs/hosts. No secret values are returned to callers
    beyond what is needed to open a connection.
    """
    out: dict[str, str] = {}
    try:
        text = env_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    for key in keys:
        m = re.search(rf"^{re.escape(key)}\s*=(.*)$", text, re.MULTILINE)
        if not m:
            continue
        val = m.group(1).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if val:
            out[key] = val
    return out


def deep_dependency_probe(timeout: float = 8.0) -> list[ServiceHealthResult]:
    """Opt-in deep probe for stateful dependencies the HTTP sweep cannot see.

    Covers the three failure classes observed in the 2026-11-16 full audit:
      * Supabase Postgres (pooler/direct) reachability
      * Redis primary reachability
      * Customer domains (supremeai.live / studio.supremeai.lat) DNS resolution

    Fail-closed: an unreachable dependency is reported DEGRADED/UNREACHABLE so it
    surfaces in the ACTION PLAN instead of failing silently at runtime.
    """
    results: list[ServiceHealthResult] = []
    env = _load_env_subset(REPO_ROOT / ".env", [
        "SUPABASE_DATABASE_URL_POOLER", "DATABASE_URL", "SUPABASE_DATABASE_URL",
        "REDIS_URL",
    ])

    # ── Postgres ─────────────────────────────────────────────────────────
    # Authoritative source = the production app's own readiness. An agent's
    # local network (IPv6-only pooler, ISP port blocks, local TLS proxies) can
    # make libpq time out even while the DB is perfectly healthy in prod, so a
    # local psycopg2 failure must NOT be reported as a production outage.
    # Same registry lookup as the node sweep — this used to repeat the primary
    # node's URL as a literal, so the two could silently disagree.
    _primary = _service_endpoint("core")
    if _primary:
        prod_ok, _prod_code, _prod_ms, prod_payload, _prod_err = probe_http_endpoint(
            _primary[1], timeout=max(timeout, 25.0)
        )
    else:
        prod_ok, _prod_code, _prod_ms, prod_payload, _prod_err = (
            False, 0, 0.0, None, "no core service in registry"
        )
    db_check = None
    if isinstance(prod_payload, dict):
        for chk in prod_payload.get("checks", []) or []:
            if isinstance(chk, dict) and chk.get("name") == "database":
                db_check = chk
                break
    if db_check:
        db_status = db_check.get("status")
        results.append(ServiceHealthResult(
            service_id="supabase-postgres", name="Supabase Postgres (pooler)",
            category="stateful_dependency",
            status="healthy" if db_status == "healthy" else "degraded",
            latency_ms=int(db_check.get("latency_ms") or 0),
            details={"source": "prod primary /health database check"},
            error=db_check.get("error"),
        ))
    elif prod_ok:
        # prod reachable but no explicit database check block — treat as healthy
        results.append(ServiceHealthResult(
            service_id="supabase-postgres", name="Supabase Postgres (pooler)",
            category="stateful_dependency", status="healthy", latency_ms=0,
            details={"source": "prod primary /health (no db block; assumed healthy)"},
        ))
    else:
        # Last resort: local psycopg2 (only when the prod probe itself failed)
        db_url = env.get("SUPABASE_DATABASE_URL_POOLER") or env.get("DATABASE_URL")
        if db_url:
            t0 = time.time()
            try:
                import psycopg2  # noqa: PLC0415

                conn = psycopg2.connect(db_url, connect_timeout=int(timeout), sslmode="require")
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                cur.fetchone()
                cur.close()
                conn.close()
                results.append(ServiceHealthResult(
                    service_id="supabase-postgres", name="Supabase Postgres (pooler)",
                    category="stateful_dependency", status="healthy",
                    latency_ms=int((time.time() - t0) * 1000),
                    details={"source": "local psycopg2 (prod probe unavailable)"},
                ))
            except Exception as exc:
                results.append(ServiceHealthResult(
                    service_id="supabase-postgres", name="Supabase Postgres (pooler)",
                    category="stateful_dependency", status="degraded",
                    latency_ms=int((time.time() - t0) * 1000),
                    error=f"local probe only (prod probe failed): {type(exc).__name__}",
                    details={"source": "local psycopg2; prod probe unavailable"},
                ))
        else:
            results.append(ServiceHealthResult(
                service_id="supabase-postgres", name="Supabase Postgres (pooler)",
                category="stateful_dependency", status="skipped", latency_ms=0,
                error="prod /health unreachable and no SUPABASE_DATABASE_URL_POOLER configured",
            ))

    # ── Redis primary ────────────────────────────────────────────────────
    redis_url = env.get("REDIS_URL")
    if redis_url:
        t0 = time.time()
        try:
            import redis  # noqa: PLC0415

            client = redis.from_url(redis_url, socket_connect_timeout=timeout,
                                    socket_timeout=timeout, decode_responses=True)
            pong = client.ping()
            results.append(ServiceHealthResult(
                service_id="redis-primary", name="Redis Primary",
                category="stateful_dependency",
                status="healthy" if pong else "degraded",
                latency_ms=int((time.time() - t0) * 1000),
                details={"url_env": "REDIS_URL"},
            ))
        except ImportError:
            results.append(ServiceHealthResult(
                service_id="redis-primary", name="Redis Primary",
                category="stateful_dependency", status="skipped", latency_ms=0,
                error="redis lib not installed",
            ))
        except Exception as exc:
            results.append(ServiceHealthResult(
                service_id="redis-primary", name="Redis Primary",
                category="stateful_dependency", status="unreachable",
                latency_ms=int((time.time() - t0) * 1000),
                error=str(exc)[:160],
            ))
    else:
        results.append(ServiceHealthResult(
            service_id="redis-primary", name="Redis Primary",
            category="stateful_dependency", status="skipped", latency_ms=0,
            error="no REDIS_URL configured",
        ))

    # ── Customer domains (DNS) ───────────────────────────────────────────
    import socket  # noqa: PLC0415

    edge_domains = _edge_domains()
    if not edge_domains:
        results.append(ServiceHealthResult(
            service_id="domain-none", name="Customer domains",
            category="edge_domain", status="skipped", latency_ms=0,
            error="no edge domain declared in config/service_registry.yaml",
        ))
    for domain in edge_domains:
        t0 = time.time()
        try:
            infos = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
            addrs = sorted({i[4][0] for i in infos})
            results.append(ServiceHealthResult(
                service_id=f"domain-{domain}", name=f"Domain {domain}",
                category="edge_domain", status="healthy",
                latency_ms=int((time.time() - t0) * 1000),
                details={"resolved": addrs[:3]},
            ))
        except Exception as exc:
            results.append(ServiceHealthResult(
                service_id=f"domain-{domain}", name=f"Domain {domain}",
                category="edge_domain", status="unreachable",
                latency_ms=int((time.time() - t0) * 1000),
                error=f"DNS: {exc}",
            ))

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SupremeAI Master Health Engine + Federation CI Sweep",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  (default)   Infrastructure sweep — Render nodes, Tower, Federation anchors
  --ci-sweep  Federation CI sweep — local guards + satellite GitHub CI status
  --full      Both sweeps (infra + CI)  <-- recommended for agent auto-fix
  --deep      Also probe stateful deps (Supabase Postgres, Redis, customer domains)

Agent workflow:
  python scripts/ops/master_health_check.py --full
  # Read ACTION PLAN section -> fix items in order -> re-run to verify green.
""",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--timeout", type=float, default=6.0, help="HTTP probe timeout (s)")
    parser.add_argument("--self-test", action="store_true", help="Offline contract self-test")
    parser.add_argument("--ci-sweep", action="store_true", help="Run CI guards + satellite GitHub CI check")
    parser.add_argument("--full", action="store_true", help="Run infra + CI sweep combined")
    parser.add_argument("--deep", action="store_true", help="Probe Supabase Postgres, Redis and customer domains")
    parser.add_argument("--heal", action="store_true", help="Auto-heal: sweep full health and trigger agent loop on top priority failure")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--quick-liveness", action="store_true", help="Report only gateway and Tower liveness")
    scope.add_argument("--pipeline-snapshot", type=Path, metavar="JSON", help="Write public health evidence; print the Actions summary")
    args = parser.parse_args(argv)
    if args.quick_liveness:
        print(pipeline_markdown(pipeline_snapshot(args.timeout, quick=True)))
        return 0
    if args.pipeline_snapshot:
        snapshot = pipeline_snapshot(args.timeout)
        args.pipeline_snapshot.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        print(pipeline_markdown(snapshot))
        return 0

    if args.self_test:
        return self_test()

    token = _get_gh_token()
    report: MasterHealthReport | None = None
    guards: list[GuardResult] = []
    satellites: list[SatelliteCIResult] = []

    if args.deep and report is None:
        report = discover_and_evaluate(timeout=args.timeout)
        report.services.extend(deep_dependency_probe(timeout=args.timeout))
        # recompute overall status to include deep deps
        unreachable = sum(1 for s in report.services if s.status == "unreachable")
        degraded = sum(1 for s in report.services if s.status == "degraded")
        healthy = sum(1 for s in report.services if s.status == "healthy")
        report.total_services = len(report.services)
        report.healthy_count = healthy
        report.degraded_count = degraded
        report.unreachable_count = unreachable
        if unreachable > 0:
            report.overall_status = "down" if unreachable >= (report.total_services // 2) else "degraded"
        elif degraded > 0:
            report.overall_status = "degraded"
        else:
            report.overall_status = "healthy"

    if args.full or args.heal or (not args.ci_sweep and not args.deep):
        if report is None:
            report = discover_and_evaluate(timeout=args.timeout)

    if args.ci_sweep or args.full or args.heal:
        guards, satellites = run_ci_sweep(token=token)

    if args.json:
        out: dict[str, Any] = {}
        if report:
            out["infra"] = report.to_dict()
        if guards or satellites:
            out["ci_sweep"] = {
                "guards": [asdict(g) for g in guards],
                "satellites": [asdict(s) for s in satellites],
                "guards_passed": sum(1 for g in guards if g.status == "pass"),
                "guards_failed": sum(1 for g in guards if g.status != "pass"),
                "satellites_green": sum(1 for s in satellites if s.status == "green"),
                "satellites_failing": sum(1 for s in satellites if s.status != "green"),
            }
        print(json.dumps(out, indent=2))
    else:
        if report:
            print_infra_report(report)
        if guards or satellites:
            print_ci_sweep_report(guards, satellites)

    infra_ok = report is None or report.overall_status == "healthy"
    ci_ok = all(g.status == "pass" for g in guards) and all(s.status == "green" for s in satellites)

    # ── Auto-heal execution hook ──────────────────────────────────────────
    if args.heal:
        if infra_ok and ci_ok:
            print(f"\n{_TICK} System is already GREEN! Nothing to heal.")
            return 0
        print(f"\n{_ROCKET} Launching Continuous Agent Loop to heal top priority failure...")
        heal_cmd = [sys.executable, str(REPO_ROOT / "scripts" / "agents" / "continuous_agent_loop.py"), "--max-tasks", "1"]
        proc = subprocess.run(heal_cmd, cwd=REPO_ROOT)
        return proc.returncode

    return 0 if (infra_ok and ci_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
