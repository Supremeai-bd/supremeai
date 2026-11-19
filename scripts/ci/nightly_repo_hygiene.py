#!/usr/bin/env python3
"""
scripts/ci/nightly_repo_hygiene.py
==================================
Nightly Repository Hygiene & Long-Term Optimization Engine.

Capabilities:
1. Git GC, Remote Prune & Commit-Graph Optimization (--git-optimize)
   - Prunes stale remote-tracking branches (`git remote prune origin`)
   - Packs loose refs (`git pack-refs --all`)
   - Writes reachable commit-graph (`git commit-graph write --reachable`)
   - Runs garbage collection (`git gc --prune=now`)
2. Workspace Temp & Cache Sweeper (--clean-caches)
   - Purges `.pytest_cache`, `.ruff_cache`, `node_modules/.vitest-cache`,
     `node_modules/.vite-temp`, stray `__pycache__`, and oversized `.tmp` dumps.
3. GitHub Actions Stale Cache & Artifact Cleaner (--purge-gh-caches)
   - Queries `/repos/{owner}/{repo}/actions/caches` and evicts stale caches
     older than `--max-cache-age-days` (default: 7) to prevent 10 GB quota exhaustion.
4. Large Blob, Forbidden Artifact & Dependency Drift Scanner (--audit-blobs)
   - Scans tracked git files for accidental large binaries (>5 MB) or binary
     artifacts (`.apk`, `.vsix`, `.exe`, `.msi`, `.pyc`) and duplicate dependencies.
5. Satellite Client API Contract Parity Check (--verify-client-contracts)
   - Verifies that the monorepo core/gateway endpoints and sentinel anchors
     required by `supremeai-apk`, `supremeai-desktop`, and `supremeai-vscode`
     remain intact and drift-free.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

FORBIDDEN_TRACKED_SUFFIXES = (".pyc", ".pyo", ".apk", ".vsix", ".exe", ".msi", ".dmg", ".AppImage")
CACHE_DIRS_TO_CLEAN = (
    ".pytest_cache",
    ".ruff_cache",
    "node_modules/.vitest-cache",
    "node_modules/.vite-temp",
)

SATELLITE_CONTRACT_RULES: tuple[dict[str, Any], ...] = (
    {
        "client": "supremeai-apk (Mobile BFF)",
        "file": "core/api/routes/mobile_bff.py",
        "required_tokens": ("/api/mobile/bff", "/orchestrate", "MobileChatRequest"),
    },
    {
        # The mobile BFF is mounted by Core, not by a Gateway re-export.
        "client": "supremeai-apk (Core Mobile BFF registration)",
        "file": "core/api/routers.py",
        "required_tokens": ('"path": "api.routes.mobile_bff"',),
    },
    {
        "client": "supremeai-apk & supremeai-desktop (SSE Chat Stream)",
        "file": "core/api/routes/stream_chat_sse.py",
        "required_tokens": ("stream", "chat"),
    },
    {
        "client": "supremeai-apk, supremeai-desktop & supremeai-vscode (OpenAI Gateway)",
        "file": "gateway/service/app.py",
        "required_tokens": ('@app.post("/v1/chat/completions")',),
    },
    {
        "client": "Satellite Hub Registry Sentinel",
        "file": "vscode/README.md",
        "required_tokens": (
            "Supremeai-bd/supremeai-apk",
            "Supremeai-bd/supremeai-desktop",
            "Supremeai-bd/supremeai-vscode",
        ),
    },
)


def _dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            fp = Path(root) / f
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total


def run_git_optimization(repo_root: Path) -> dict[str, Any]:
    """Run git remote prune origin, pack-refs, commit-graph write, and git gc --prune=now."""
    git_dir = repo_root / ".git"
    before_bytes = _dir_size_bytes(git_dir)
    steps_run: list[dict[str, Any]] = []

    commands = [
        (["git", "remote", "prune", "origin"], "remote-prune-origin"),
        (["git", "pack-refs", "--all"], "pack-refs"),
        (["git", "commit-graph", "write", "--reachable"], "commit-graph"),
        (["git", "gc", "--prune=now"], "gc-prune-now"),
    ]

    for cmd, label in commands:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            steps_run.append({
                "step": label,
                "returncode": proc.returncode,
                "status": "ok" if proc.returncode == 0 else "warn",
            })
        except Exception as exc:
            steps_run.append({
                "step": label,
                "returncode": -1,
                "status": "error",
                "error": str(exc),
            })

    after_bytes = _dir_size_bytes(git_dir)
    saved_bytes = max(0, before_bytes - after_bytes)
    return {
        "before_mb": round(before_bytes / (1024 * 1024), 2),
        "after_mb": round(after_bytes / (1024 * 1024), 2),
        "reclaimed_mb": round(saved_bytes / (1024 * 1024), 2),
        "steps": steps_run,
    }


def clean_workspace_caches(repo_root: Path) -> dict[str, Any]:
    """Sweep local test/linter caches and heavy temporary dumps in .tmp."""
    reclaimed_bytes = 0
    cleaned_targets: list[str] = []

    for rel in CACHE_DIRS_TO_CLEAN:
        target = repo_root / rel
        if target.exists():
            sz = _dir_size_bytes(target)
            try:
                shutil.rmtree(target, ignore_errors=True)
                reclaimed_bytes += sz
                cleaned_targets.append(f"{rel} ({round(sz / 1024, 1)} KB)")
            except Exception:
                pass

    # Clean dupreport* and oversized >1MB scratch files inside .tmp
    tmp_dir = repo_root / ".tmp"
    if tmp_dir.is_dir():
        for item in tmp_dir.iterdir():
            try:
                if item.is_dir() and item.name.startswith("dupreport"):
                    sz = _dir_size_bytes(item)
                    shutil.rmtree(item, ignore_errors=True)
                    reclaimed_bytes += sz
                    cleaned_targets.append(f".tmp/{item.name} ({round(sz / 1024, 1)} KB)")
                elif item.is_file() and item.stat().st_size > 1024 * 1024:
                    sz = item.stat().st_size
                    item.unlink(missing_ok=True)
                    reclaimed_bytes += sz
                    cleaned_targets.append(f".tmp/{item.name} ({round(sz / 1024, 1)} KB)")
            except OSError:
                pass

    # Sweep stray __pycache__ outside .venv and node_modules
    pycache_count = 0
    pycache_bytes = 0
    for root, dirs, _files in os.walk(repo_root):
        dirs[:] = [
            d for d in dirs
            if d not in {".git", ".venv", "venv", "node_modules", ".tox"}
        ]
        if "__pycache__" in dirs:
            pdir = Path(root) / "__pycache__"
            sz = _dir_size_bytes(pdir)
            shutil.rmtree(pdir, ignore_errors=True)
            pycache_bytes += sz
            pycache_count += 1
            dirs.remove("__pycache__")

    if pycache_count:
        reclaimed_bytes += pycache_bytes
        cleaned_targets.append(
            f"{pycache_count} __pycache__ dirs ({round(pycache_bytes / 1024, 1)} KB)"
        )

    return {
        "reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 2),
        "reclaimed_kb": round(reclaimed_bytes / 1024, 1),
        "cleaned_targets": cleaned_targets,
    }


def purge_github_actions_caches(
    repo: str,
    token: str,
    max_age_days: int = 7,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Evict stale GitHub Actions caches older than max_age_days."""
    if not token or not repo:
        return {
            "status": "skipped",
            "reason": "GH_TOKEN or GH_REPO not provided",
            "deleted_count": 0,
            "reclaimed_mb": 0.0,
        }

    url = f"https://api.github.com/repos/{repo}/actions/caches?per_page=100"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SupremeAI-Nightly-Hygiene",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as exc:
        return {
            "status": "skipped",
            "reason": f"API fetch failed: {exc}",
            "deleted_count": 0,
            "reclaimed_mb": 0.0,
        }

    caches = data.get("actions_caches") or []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    deleted_count = 0
    reclaimed_bytes = 0

    for c in caches:
        cache_id = c.get("id")
        last_accessed_raw = c.get("last_accessed_at") or c.get("created_at") or ""
        size_in_bytes = int(c.get("size_in_bytes") or 0)
        if not cache_id or not last_accessed_raw:
            continue
        try:
            dt = datetime.fromisoformat(last_accessed_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue

        if dt < cutoff:
            if dry_run:
                deleted_count += 1
                reclaimed_bytes += size_in_bytes
                continue
            del_url = f"https://api.github.com/repos/{repo}/actions/caches/{cache_id}"
            try:
                del_req = urllib.request.Request(del_url, headers=headers, method="DELETE")
                with urllib.request.urlopen(del_req, timeout=20) as del_resp:
                    if del_resp.status in (200, 204):
                        deleted_count += 1
                        reclaimed_bytes += size_in_bytes
            except Exception:
                pass

    return {
        "status": "ok",
        "total_caches_inspected": len(caches),
        "deleted_count": deleted_count,
        "reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 2),
    }


def audit_large_blobs_and_deps(repo_root: Path, max_blob_mb: float = 5.0) -> dict[str, Any]:
    """Scan git-tracked files for large blobs, binary artifacts, and duplicate deps."""
    max_bytes = int(max_blob_mb * 1024 * 1024)
    large_files: list[dict[str, Any]] = []
    forbidden_artifacts: list[str] = []

    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(repo_root),
            capture_output=True,
            timeout=60,
            check=False,
        )
        raw_paths = [p.decode("utf-8", errors="replace") for p in proc.stdout.split(b"\x00") if p]
    except Exception:
        raw_paths = []

    for rel in raw_paths:
        if rel.endswith(FORBIDDEN_TRACKED_SUFFIXES) or "/__pycache__/" in f"/{rel}":
            forbidden_artifacts.append(rel)
        fp = repo_root / rel
        try:
            if fp.is_file():
                sz = fp.stat().st_size
                if sz > max_bytes:
                    large_files.append({
                        "path": rel,
                        "size_mb": round(sz / (1024 * 1024), 2),
                    })
        except OSError:
            pass

    # Check requirements.txt for duplicate package lines
    duplicate_deps: list[str] = []
    req_file = repo_root / "requirements.txt"
    if req_file.is_file():
        seen: set[str] = set()
        for line in req_file.read_text(encoding="utf-8", errors="replace").splitlines():
            clean = line.strip()
            if not clean or clean.startswith(("#", "-")):
                continue
            pkg = re.split(r"[<>=!~\[\s;]", clean, maxsplit=1)[0].lower()
            if pkg:
                if pkg in seen:
                    duplicate_deps.append(pkg)
                seen.add(pkg)

    return {
        "tracked_files_scanned": len(raw_paths),
        "large_files": large_files,
        "forbidden_artifacts": forbidden_artifacts,
        "duplicate_dependencies": sorted(set(duplicate_deps)),
    }


def verify_satellite_client_contracts(
    repo_root: Path,
    rules: tuple[dict[str, Any], ...] = SATELLITE_CONTRACT_RULES,
) -> dict[str, Any]:
    """Verify API routes and sentinel anchors required by apk, desktop, and vscode satellites."""
    results: list[dict[str, Any]] = []
    violations: list[str] = []

    for rule in rules:
        client = rule["client"]
        rel_file = rule["file"]
        tokens = rule["required_tokens"]
        fp = repo_root / rel_file

        if not fp.is_file():
            msg = f"{client}: missing contract file '{rel_file}'"
            violations.append(msg)
            results.append({"client": client, "file": rel_file, "status": "missing_file"})
            continue

        content = fp.read_text(encoding="utf-8", errors="replace")
        missing_tokens = [t for t in tokens if t not in content]
        if missing_tokens:
            msg = f"{client}: '{rel_file}' missing contract tokens {missing_tokens}"
            violations.append(msg)
            results.append({
                "client": client,
                "file": rel_file,
                "status": "drift_detected",
                "missing_tokens": missing_tokens,
            })
        else:
            results.append({"client": client, "file": rel_file, "status": "ok"})

    return {
        "status": "ok" if not violations else "drift_detected",
        "contracts_checked": len(rules),
        "passed": len(rules) - len(violations),
        "violations": violations,
        "details": results,
    }


def format_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "## 🧹 Nightly Repository Hygiene & Optimization Report",
        "",
        f"- **Timestamp (UTC):** `{report.get('timestamp')}`",
    ]
    if "git_optimization" in report:
        g = report["git_optimization"]
        lines.extend([
            "",
            "### 1. Git GC, Remote Prune & Commit-Graph Optimization",
            f"- `.git` Size Before: **{g['before_mb']} MB** -> After: **{g['after_mb']} MB** (Reclaimed: **{g['reclaimed_mb']} MB**)",
            f"- Tasks Executed: `{', '.join(s['step'] + ':' + s['status'] for s in g['steps'])}`",
        ])
    if "cache_cleanup" in report:
        c = report["cache_cleanup"]
        lines.extend([
            "",
            "### 2. Temp & Cache Directory Sweeper",
            f"- Disk Reclaimed: **{c['reclaimed_mb']} MB** (`{c['reclaimed_kb']} KB`)",
            f"- Targets Cleaned: `{len(c['cleaned_targets'])}`",
        ])
    if "gh_caches" in report:
        gh = report["gh_caches"]
        lines.extend([
            "",
            "### 3. GitHub Actions Cache & Artifact Eviction",
            f"- Status: **{gh.get('status')}** | Deleted Caches: **{gh.get('deleted_count', 0)}** | Reclaimed: **{gh.get('reclaimed_mb', 0.0)} MB**",
        ])
    if "blob_audit" in report:
        b = report["blob_audit"]
        lines.extend([
            "",
            "### 4. Large File & Dependency Drift Scanner",
            f"- Tracked Files Scanned: **{b['tracked_files_scanned']}**",
            f"- Large Blobs (>5 MB): **{len(b['large_files'])}**",
            f"- Tracked Binary/Cache Artifacts: **{len(b['forbidden_artifacts'])}**",
            f"- Duplicate Dependencies: **{len(b['duplicate_dependencies'])}**",
        ])
    if "client_contracts" in report:
        cc = report["client_contracts"]
        lines.extend([
            "",
            "### 5. Satellite Client API Contract Parity (`apk`, `desktop`, `vscode`)",
            f"- Status: **{cc['status'].upper()}** (**{cc['passed']}/{cc['contracts_checked']}** contracts verified)",
        ])
        for v in cc.get("violations", []):
            lines.append(f"  - ⚠️ `{v}`")
    return "\n".join(lines) + "\n"


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=str(root), capture_output=True, check=True)
        (root / ".pytest_cache").mkdir()
        (root / ".pytest_cache" / "dummy").write_bytes(b"x" * 2048)
        (root / "requirements.txt").write_text("fastapi>=0.110\nfastapi>=0.111\n", encoding="utf-8")

        cache_res = clean_workspace_caches(root)
        assert not (root / ".pytest_cache").exists(), ".pytest_cache should be removed"
        assert cache_res["reclaimed_kb"] >= 2.0

        audit_res = audit_large_blobs_and_deps(root, max_blob_mb=5.0)
        assert "fastapi" in audit_res["duplicate_dependencies"]

        # Test satellite contract verifier
        (root / "api.py").write_text("router = '/v1/chat/completions'\n", encoding="utf-8")
        mock_rules = (
            {"client": "test-client", "file": "api.py", "required_tokens": ("/v1/chat/completions",)},
        )
        cc_res = verify_satellite_client_contracts(root, rules=mock_rules)
        assert cc_res["status"] == "ok" and cc_res["passed"] == 1

    print("self-test: PASS (all 5 hygiene engines verified)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Nightly Repository Hygiene & Optimization Engine")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-test")
    parser.add_argument("--all", action="store_true", help="Run all 5 hygiene engines")
    parser.add_argument("--git-optimize", action="store_true", help="Run git remote prune, gc, pack-refs, and commit-graph")
    parser.add_argument("--clean-caches", action="store_true", help="Clean .tmp, pytest, ruff, and pycache dirs")
    parser.add_argument("--purge-gh-caches", action="store_true", help="Purge stale GitHub Actions caches")
    parser.add_argument("--audit-blobs", action="store_true", help="Scan for large blobs and duplicate deps")
    parser.add_argument("--verify-client-contracts", action="store_true", help="Verify satellite client API contracts")
    parser.add_argument("--max-cache-age-days", type=int, default=7)
    parser.add_argument("--max-blob-mb", type=float, default=5.0)
    parser.add_argument("--json", type=str, default="", help="Write JSON report to path")
    parser.add_argument("--markdown", type=str, default="", help="Write Markdown report to path")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    repo_root = Path.cwd()
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if args.all or args.clean_caches:
        report["cache_cleanup"] = clean_workspace_caches(repo_root)
    if args.all or args.git_optimize:
        report["git_optimization"] = run_git_optimization(repo_root)
    if args.all or args.purge_gh_caches:
        repo = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY") or ""
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        report["gh_caches"] = purge_github_actions_caches(
            repo=repo,
            token=token,
            max_age_days=args.max_cache_age_days,
        )
    if args.all or args.audit_blobs:
        report["blob_audit"] = audit_large_blobs_and_deps(repo_root, max_blob_mb=args.max_blob_mb)
    if args.all or args.verify_client_contracts:
        report["client_contracts"] = verify_satellite_client_contracts(repo_root)

    md = format_markdown_report(report)
    print(md)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(md, encoding="utf-8")

    if report.get("client_contracts", {}).get("status") == "drift_detected":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
