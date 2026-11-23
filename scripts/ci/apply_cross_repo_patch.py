#!/usr/bin/env python3
"""
scripts/ci/apply_cross_repo_patch.py
Applies cross-repo patch files (.patches/public/*.patch or .patches/private/*.patch)
to a target repository and creates an auto-sync Pull Request.

Part of Living Protocol 10: Bi-Directional Cross-Repo Patch Protocol.

Usage:
    python scripts/ci/apply_cross_repo_patch.py \
        --patch-dir .patches/public \
        --target-dir ../supremeai-public \
        --target-repo Supremeai-bd/supremeai-public \
        [--dry-run | --apply | --create-pr]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def is_loop_prevented(actor: str | None = None) -> bool:
    """বাংলা মন্তব্য: বটের তৈরি PR বা অ্যাকশন থেকে সার্কুলার লুপ প্রতিরোধে গার্ড ফাংশন।"""
    current_actor = actor or os.getenv("GITHUB_ACTOR", "")
    blocked_actors = {
        "github-actions[bot]",
        "app/github-actions",
        "dependabot[bot]",
        "renovate[bot]",
    }
    return current_actor.lower() in blocked_actors


def find_patches(patch_dir: Path) -> list[Path]:
    """বাংলা মন্তব্য: প্যাচ ডিরেক্টরি থেকে সমস্ত বৈধ .patch ও .diff ফাইল খুঁজে বের করা।"""
    if not patch_dir.exists() or not patch_dir.is_dir():
        return []
    patches = sorted(
        [p for p in patch_dir.glob("*") if p.suffix.lower() in {".patch", ".diff"} and p.is_file()]
    )
    return patches


def validate_patch(patch_path: Path) -> tuple[bool, str]:
    """বাংলা মন্তব্য: প্যাচ ফাইলের সাইজ ও প্রাথমিক ফরম্যাট যাচাই করা।"""
    if not patch_path.exists():
        return False, f"Patch file not found: {patch_path}"
    content = patch_path.read_text(encoding="utf-8", errors="replace").strip()
    if not content:
        return False, f"Patch file is empty: {patch_path.name}"
    # Standard diff/patch headers check
    valid_markers = ("diff --git", "--- ", "+++ ", "Index:", "PATCH")
    if not any(marker in content for marker in valid_markers):
        return False, f"Invalid patch format: {patch_path.name} (missing diff headers)"
    return True, "Valid"


def verify_patch_apply(target_dir: Path, patch_path: Path) -> tuple[bool, str]:
    """বাংলা মন্তব্য: git apply --check চালিয়ে প্যাচ কনফ্লিক্ট মুক্ত কিনা তা যাচাই করা।"""
    try:
        proc = subprocess.run(
            ["git", "apply", "--check", str(patch_path.resolve())],
            cwd=target_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return True, "Patch checks cleanly."
        return False, proc.stderr.strip() or proc.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def apply_patch(target_dir: Path, patch_path: Path) -> tuple[bool, str]:
    """বাংলা মন্তব্য: টার্গেট রিপোজিটরিতে প্যাচ সরাসরি অ্যাপ্লাই করা।"""
    try:
        proc = subprocess.run(
            ["git", "apply", str(patch_path.resolve())],
            cwd=target_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return True, f"Successfully applied {patch_path.name}"
        return False, proc.stderr.strip() or proc.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def create_sync_pr(
    target_dir: Path,
    target_repo: str,
    source_repo: str,
    applied_patches: list[str],
    source_ref: str = "main",
) -> bool:
    """বাংলা মন্তব্য: টার্গেট রিপোজিটরিতে নতুন ব্রাঞ্চ তৈরি, পুশ এবং auto-sync লেবেলসহ PR খোলা।"""
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=target_dir, text=True)
    if not status.strip():
        print("  [skip] No file diff in target repo after applying patches.")
        return False

    slug = "-".join([p.replace(".patch", "").replace(".diff", "") for p in applied_patches[:3]])
    branch_name = f"sync/patch-{slug[:30]}"

    print(f"  [git] Configuring bot identity and checkout branch '{branch_name}'...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=target_dir, check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=target_dir, check=True)
    subprocess.run(["git", "checkout", "-B", branch_name], cwd=target_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=target_dir, check=True)

    commit_msg = f"chore(sync): cross-repo patch sync from {source_repo}\n\nApplied patches:\n" + "\n".join(f"- {p}" for p in applied_patches)
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=target_dir, check=True)
    subprocess.run(["git", "push", "-u", "origin", branch_name, "--force"], cwd=target_dir, check=True)

    # Check if PR already exists
    try:
        existing_pr = subprocess.check_output(
            ["gh", "pr", "list", "--repo", target_repo, "--head", branch_name, "--state", "open", "--json", "number", "--jq", ".[0].number"],
            cwd=target_dir,
            text=True,
        ).strip()
    except Exception:
        existing_pr = ""

    if existing_pr and existing_pr != "null":
        print(f"  [ok] Open PR #{existing_pr} already exists for {branch_name}; updated via push.")
        return True

    pr_body = (
        f"## Automated Cross-Repo Patch Synchronization\n\n"
        f"- **Source Repo:** `{source_repo}` (`{source_ref}`)\n"
        f"- **Applied Patches:**\n"
        + "\n".join(f"  - `{p}`" for p in applied_patches)
        + "\n\n### বাংলা বিবরণ\n"
        f"সোর্স রিপোজিটরি `{source_repo}`-এর পরিবর্তনের পরিপ্রেক্ষিতে এই প্যাচটি স্বয়ংক্রিয়ভাবে প্রয়োগ করে PR তৈরি করা হয়েছে।\n\n"
        f"> 🛡️ **Loop Guard Active:** Tagged with `auto-sync` label to prevent circular triggers.\n"
    )

    # বাংলা মন্তব্য: রিমোট টার্গেট রিপোতে auto-sync লেবেল নিশ্চিত করা
    try:
        subprocess.run(
            [
                "gh", "label", "create", "auto-sync",
                "--description", "Automated cross-repo patch synchronization",
                "--color", "0e8a16",
                "--force",
                "--repo", target_repo,
            ],
            cwd=target_dir,
            capture_output=True,
        )
    except Exception:
        pass

    pr_cmd = [
        "gh", "pr", "create",
        "--repo", target_repo,
        "--title", f"chore(sync): automated cross-repo patch from {source_repo}",
        "--body", pr_body,
        "--head", branch_name,
        "--base", "main",
    ]
    try:
        subprocess.run(pr_cmd, cwd=target_dir, check=True)
        print(f"  [success] Successfully created PR in {target_repo}!")
        # Add auto-sync label defensively
        try:
            subprocess.run(
                ["gh", "pr", "edit", branch_name, "--repo", target_repo, "--add-label", "auto-sync"],
                cwd=target_dir,
                capture_output=True,
            )
        except Exception:
            pass
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  [error] Failed to create PR in {target_repo}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply cross-repo patches and open synchronization PRs.")
    parser.add_argument("--patch-dir", type=str, default=".patches/public", help="Directory containing .patch files")
    parser.add_argument("--target-dir", type=str, required=True, help="Path to local checkout of target repository")
    parser.add_argument("--target-repo", type=str, default="Supremeai-bd/supremeai-public", help="GitHub target repo slug")
    parser.add_argument("--source-repo", type=str, default="Supremeai-bd/supremeai", help="GitHub source repo slug")
    parser.add_argument("--source-ref", type=str, default="main", help="Source git reference or PR number")
    parser.add_argument("--dry-run", action="store_true", help="Only validate and check without applying")
    parser.add_argument("--apply", action="store_true", help="Apply patches to target directory")
    parser.add_argument("--create-pr", action="store_true", help="Commit applied changes and create GitHub PR")
    args = parser.parse_args()

    # 1. Loop Guard
    if is_loop_prevented():
        print("[apply_cross_repo_patch] Loop guard active (bot actor detected). Skipping to prevent circular ping-pong.")
        return 0

    patch_dir = Path(args.patch_dir).resolve()
    target_dir = Path(args.target_dir).resolve()

    if not target_dir.exists():
        print(f"Error: Target directory does not exist: {target_dir}")
        return 1

    patches = find_patches(patch_dir)
    if not patches:
        print(f"[apply_cross_repo_patch] No patch files found in {patch_dir}. Nothing to apply.")
        return 0

    print(f"=== SupremeAI Cross-Repo Patch Applicator ===")
    print(f"Found {len(patches)} patch file(s) in {patch_dir.name}:")
    for p in patches:
        print(f"  - {p.name}")

    # Validate all patches first
    for p in patches:
        valid, msg = validate_patch(p)
        if not valid:
            print(f"Error validating {p.name}: {msg}")
            return 1
        can_apply, check_msg = verify_patch_apply(target_dir, p)
        if not can_apply:
            print(f"Conflict error for {p.name} on {target_dir.name}:\n{check_msg}")
            return 1

    print("All patches validated cleanly against target repo.")

    if args.dry_run:
        print("[dry-run] Dry run completed successfully. All patches apply cleanly.")
        return 0

    applied: list[str] = []
    if args.apply or args.create_pr:
        for p in patches:
            success, apply_msg = apply_patch(target_dir, p)
            if not success:
                print(f"Failed to apply {p.name}: {apply_msg}")
                return 1
            print(f"  [applied] {p.name}")
            applied.append(p.name)

    if args.create_pr and applied:
        pr_ok = create_sync_pr(
            target_dir=target_dir,
            target_repo=args.target_repo,
            source_repo=args.source_repo,
            applied_patches=applied,
            source_ref=args.source_ref,
        )
        if not pr_ok:
            return 1

    print("\n[apply_cross_repo_patch] Execution completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
