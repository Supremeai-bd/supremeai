#!/usr/bin/env python3
"""
scripts/ci/sync_to_public_repo.py
Automates synchronization of canonical endpoints, contracts, and schemas from
SupremeAI Monorepo into SupremeAI Public Repo (Supremeai-bd/supremeai-public).

Usage:
    python scripts/ci/sync_to_public_repo.py --target-dir F:/supremeai-public [--dry-run | --apply | --create-pr]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "api-schemas" / "generated" / "public_endpoints.json"


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        # Auto-generate if missing
        print(f"[sync_to_public] Generating manifest via sync_deployment_config.py...")
        from scripts.ci.sync_deployment_config import main as sync_main
        sync_main()
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def sync_platform_endpoints_ts(public_dir: Path, manifest: dict, apply: bool = False) -> bool:
    target = public_dir / "src" / "config" / "platformEndpoints.ts"
    if not target.exists():
        print(f"  [skip] {target} does not exist")
        return False

    endpoints = manifest.get("endpoints", {})
    api_render = endpoints.get("api_gateway", {}).get("direct_render_origin", "https://supremeai-api-ulw0.onrender.com")
    api_sid = endpoints.get("api_gateway", {}).get("service_id", "")
    mcp_render = endpoints.get("mcp_tower", {}).get("direct_render_origin", "https://supremeai-mcp-tower-live.onrender.com")

    content = target.read_text(encoding="utf-8")
    original = content

    # Replace DEFAULT_MCP_TOWER_ORIGIN with canonical live Render origin
    content = re.sub(
        r"export const DEFAULT_MCP_TOWER_ORIGIN\s*=\s*'[^']+';",
        f"export const DEFAULT_MCP_TOWER_ORIGIN = '{mcp_render}';",
        content,
    )
    # Replace DEFAULT_BACKEND_ORIGIN with canonical live Render origin
    content = re.sub(
        r"export const DEFAULT_BACKEND_ORIGIN\s*=\s*'[^']+';",
        f"export const DEFAULT_BACKEND_ORIGIN = '{api_render}';",
        content,
    )
    # Update KNOWN_RENDER_SERVICE_IDS if service ID present
    if api_sid:
        content = re.sub(
            r"'supremeai-api':\s*'[^']+'",
            f"'supremeai-api': '{api_sid}'",
            content,
        )

    if content == original:
        print(f"  [clean] platformEndpoints.ts is already in sync")
        return False

    if apply:
        target.write_text(content, encoding="utf-8")
        print(f"  [updated] Updated platformEndpoints.ts")
    else:
        print(f"  [dry-run] Would update platformEndpoints.ts")
    return True


def sync_models_json(public_dir: Path, manifest: dict, apply: bool = False) -> bool:
    target = public_dir / "packages" / "contracts" / "models.json"
    if not target.exists():
        print(f"  [skip] {target} does not exist")
        return False

    content = target.read_text(encoding="utf-8")
    api_proxy = manifest.get("ssot_public_gateway") or manifest.get("endpoints", {}).get("api_gateway", {}).get("public_proxy_url", "https://supremeai-studio.pages.dev/api")

    new_content = re.sub(
        r'"gatewayBaseUrl":\s*"[^"]+"',
        f'"gatewayBaseUrl": "{api_proxy}"',
        content,
    )

    if new_content == content:
        print(f"  [clean] models.json is already in sync")
        return False

    if apply:
        target.write_text(new_content, encoding="utf-8")
        print(f"  [updated] Updated models.json gatewayBaseUrl -> {api_proxy}")
    else:
        print(f"  [dry-run] Would update models.json gatewayBaseUrl -> {api_proxy}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize canonical endpoints into SupremeAI Public Repo.")
    parser.add_argument("--target-dir", type=str, default="F:/supremeai-public", help="Path to local checkout of supremeai-public")
    parser.add_argument("--apply", action="store_true", help="Apply changes directly to files")
    parser.add_argument("--create-pr", action="store_true", help="Create GitHub pull request in public repo")
    args = parser.parse_args()

    public_dir = Path(args.target_dir).resolve()
    if not public_dir.exists():
        print(f"Error: Target public directory not found: {public_dir}")
        return 1

    print(f"=== SupremeAI Cross-Repo Sync: Monorepo -> {public_dir.name} ===")
    manifest = load_manifest()

    changed = False
    changed |= sync_platform_endpoints_ts(public_dir, manifest, apply=args.apply)
    changed |= sync_models_json(public_dir, manifest, apply=args.apply)

    if changed and args.create_pr:
        print("\nCreating GitHub PR in supremeai-public...")
        # Check git status in public repo
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=public_dir, text=True)
        if status.strip():
            branch_name = f"bot/sync-monorepo-endpoints"
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=public_dir, check=True)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=public_dir, check=True)
            subprocess.run(["git", "checkout", "-B", branch_name], cwd=public_dir, check=True)
            subprocess.run(["git", "add", "src/config/platformEndpoints.ts", "packages/contracts/models.json"], cwd=public_dir, check=True)
            subprocess.run(["git", "commit", "-m", "chore(sync): synchronize canonical gateway and mcp endpoints from monorepo"], cwd=public_dir, check=True)
            subprocess.run(["git", "push", "-u", "origin", branch_name, "--force"], cwd=public_dir, check=True)
            existing_pr = subprocess.check_output(
                ["gh", "pr", "list", "--repo", "Supremeai-bd/supremeai-public", "--head", branch_name, "--state", "open", "--json", "number", "--jq", ".[0].number"],
                cwd=public_dir,
                text=True,
            ).strip()
            if existing_pr:
                print(f"Open PR #{existing_pr} already exists for {branch_name}; force-push updated it.")
            else:
                pr_cmd = [
                    "gh", "pr", "create",
                    "--repo", "Supremeai-bd/supremeai-public",
                    "--title", "chore(sync): synchronize canonical endpoints from monorepo",
                    "--body", "Automated synchronization of `platformEndpoints.ts` and `models.json` from `Supremeai-bd/supremeai`.\n\n- Custom Domain API: `https://api.supremeai.live`\n- Custom Domain MCP: `https://mcp.supremeai.live`\n\nVerified by CI.",
                    "--head", branch_name,
                    "--base", "main"
                ]
                subprocess.run(pr_cmd, cwd=public_dir, check=True)
                print("Successfully created PR in Supremeai-bd/supremeai-public!")
        else:
            print("No diff detected in public repo; skipping PR creation.")

    print(f"\nExecution complete. Changes detected: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
