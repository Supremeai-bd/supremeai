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
    raw = patch_path.read_bytes()
    if not raw.strip():
        return False, f"Patch file is empty: {patch_path.name}"
    content = ""
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    content = content.strip()
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


def get_patch_targets(patch_path: Path) -> list[str]:
    """বাংলা মন্তব্য: git apply --numstat চালিয়ে প্যাচে অন্তর্ভুক্ত ফাইলগুলোর সুনির্দিষ্ট তালিকা বের করা।"""
    try:
        proc = subprocess.run(
            ["git", "apply", "--numstat", str(patch_path.resolve())],
            capture_output=True,
            text=True,
            check=True,
        )
        files = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                files.append(parts[2].strip().strip('"'))
        return files
    except Exception:
        return []


def is_already_applied(target_dir: Path, patch_path: Path) -> bool:
    """Reverse-check: patch already landed on target (git apply --reverse --check)."""
    try:
        proc = subprocess.run(
            ["git", "apply", "--reverse", "--check", str(patch_path.resolve())],
            cwd=target_dir,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0
    except Exception:
        return False


def create_source_cleanup_pr(
    source_repo: str,
    applied_patches: list[Path],
    source_dir: Path | None = None,
) -> bool:
    """Rule #10 loop-stop: after target auto-sync PR opens, open a source-repo PR
    that deletes the consumed .patches/ inputs so later pushes do not re-sync.

    Requires GH_TOKEN (CI). source_dir defaults to cwd (pipeline source root).
    Missing files → no-op success (already consumed).
    """
    src = (source_dir or Path.cwd()).resolve()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("  [cleanup-skip] GH_TOKEN/GITHUB_TOKEN not set; open source cleanup PR manually.")
        return False

    rels: list[str] = []
    for p in applied_patches:
        try:
            rels.append(str(p.resolve().relative_to(src)))
        except ValueError:
            rels.append(str(p))
    if not rels:
        return False

    existing = [r for r in rels if (src / r).exists()]
    if not existing:
        print("  [cleanup] patch file(s) already removed from source; nothing to do.")
        return True

    slug = "-".join(Path(r).stem for r in existing[:3])[:30]
    branch_name = f"sync/consume-{slug}"

    print(f"  [cleanup] Opening source PR to consume patches on {source_repo} ({branch_name})...")
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=src, check=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=src, check=True)
        subprocess.run(["git", "checkout", "-B", branch_name], cwd=src, check=True)
        subprocess.run(["git", "rm", "--"] + existing, cwd=src, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"  [cleanup-error] git prepare failed: {exc}")
        return False

    commit_msg = (
        "chore(sync): consume cross-repo patches (Rule #10 loop-stop)\n\n"
        "Auto-removed after target auto-sync PR opened:\n"
        + "\n".join(f"- {r}" for r in existing)
    )
    try:
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=src, check=True)
        subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=src, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"  [cleanup-error] git commit/push failed: {exc}")
        return False

    try:
        existing_pr = subprocess.check_output(
            ["gh", "pr", "list", "--repo", source_repo, "--head", branch_name, "--state", "open", "--json", "number", "--jq", ".[0].number"],
            cwd=src,
            text=True,
        ).strip()
    except Exception:
        existing_pr = ""
    if existing_pr and existing_pr != "null":
        print(f"  [cleanup-ok] Source cleanup PR #{existing_pr} already open for {branch_name}.")
        return True

    pr_body = (
        "## Rule #10 loop-stop — consume cross-repo patch inputs\n\n"
        "Target auto-sync PR has been opened (or content already landed). "
        "This PR deletes the input patch file(s) from `.patches/` so future pushes "
        "do not re-sync (force-push same branch).\n\n"
        "### Removed\n"
        + "\n".join(f"- `{r}`" for r in existing)
        + "\n\n> Loop-guard: merge only after the corresponding target PR is healthy (open or merged)."
    )
    try:
        subprocess.run(
            [
                "gh", "pr", "create",
                "--repo", source_repo,
                "--title", f"chore(sync): consume cross-repo patches ({slug})",
                "--body", pr_body,
                "--head", branch_name,
                "--base", "main",
            ],
            cwd=src,
            check=True,
        )
        print(f"  [cleanup-success] Source cleanup PR opened on {source_repo}.")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  [cleanup-error] Failed to open source cleanup PR: {exc}")
        return False


def create_sync_pr(
    target_dir: Path,
    target_repo: str,
    source_repo: str,
    applied_patches: list[Path],
    source_ref: str = "main",
) -> bool:
    """বাংলা মন্তব্য: টার্গেট রিপোজিটরিতে নতুন ব্রাঞ্চ তৈরি, পুশ এবং auto-sync লেবেলসহ PR খোলা।"""
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=target_dir, text=True)
    if not status.strip():
        print("  [skip] No file diff in target repo after applying patches.")
        return False

    # বাংলা মন্তব্য: git apply --numstat থেকে নিখুঁতভাবে শুধুমাত্র প্যাচের টার্গেট ফাইলগুলো স্টেজ করা
    files_to_stage = set()
    for p in applied_patches:
        files_to_stage.update(get_patch_targets(p))

    # Fallback to status if numstat is empty
    if not files_to_stage:
        for line in status.splitlines():
            if line.strip():
                files_to_stage.add(line[3:].strip().strip('"'))

    if not files_to_stage:
        print("  [skip] No file diff in target repo after applying patches.")
        return False

    patch_names = [p.name for p in applied_patches]
    slug = "-".join([p.stem for p in applied_patches[:3]])
    branch_name = f"sync/patch-{slug[:30]}"

    print(f"  [git] Configuring bot identity and checkout branch '{branch_name}'...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=target_dir, check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=target_dir, check=True)
    subprocess.run(["git", "checkout", "-B", branch_name], cwd=target_dir, check=True)

    print(f"  [git] Staging {len(files_to_stage)} targeted file(s) strictly from patches...")
    subprocess.run(["git", "add", "--"] + sorted(files_to_stage), cwd=target_dir, check=True)

    commit_msg = f"chore(sync): cross-repo patch sync from {source_repo}\n\nApplied patches:\n" + "\n".join(f"- {p}" for p in patch_names)
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

    # Validate all patches first. Already-landed content (reverse-check) is
    # NOT a conflict — it means the target auto-sync PR already merged; we
    # only need Rule #10 loop-stop cleanup on the source side.
    pending: list[Path] = []
    already: list[Path] = []
    for p in patches:
        valid, msg = validate_patch(p)
        if not valid:
            print(f"Error validating {p.name}: {msg}")
            return 1
        can_apply, check_msg = verify_patch_apply(target_dir, p)
        if can_apply:
            pending.append(p)
        elif is_already_applied(target_dir, p):
            print(f"  [already-landed] {p.name} — reverse-check OK; source cleanup only.")
            already.append(p)
        else:
            print(f"Conflict error for {p.name} on {target_dir.name}:\n{check_msg}")
            return 1

    if pending:
        print(f"All pending patches validated cleanly ({len(pending)} to apply).")

    if args.dry_run:
        if already and not pending:
            print("[dry-run] All patches already landed on target; source cleanup would run on --create-pr.")
        else:
            print("[dry-run] Dry run completed successfully. All pending patches apply cleanly.")
        return 0

    if already and not pending:
        # Target content already merged (auto-sync PR landed) — Rule #10 loop-stop:
        # consume the input patch files on the source side only.
        # Cleanup is BEST-EFFORT: a push/PR failure here must not fail the sync job
        # (the target side is already consistent).
        print("All patches already landed on target — running source cleanup only.")
        try:
            cleaned = create_source_cleanup_pr(args.source_repo, already, source_dir=ROOT)
            if not cleaned:
                print("  [cleanup-warn] source cleanup did not complete; open a delete PR for the patch file(s) manually.")
        except Exception as exc:
            print(f"  [cleanup-warn] source cleanup raised: {exc}")
        print("\n[apply_cross_repo_patch] Execution completed successfully.")
        return 0

    applied: list[Path] = []
    if args.apply or args.create_pr:
        for p in pending:
            success, apply_msg = apply_patch(target_dir, p)
            if not success:
                print(f"Failed to apply {p.name}: {apply_msg}")
                return 1
            print(f"  [applied] {p.name}")
            applied.append(p)

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
        # Rule #10 loop-stop: target auto-sync PR is open → consume source inputs
        # (include any already-landed siblings from a mixed batch). Best-effort:
        # target PR is already open — cleanup failure must not fail this job.
        try:
            create_source_cleanup_pr(args.source_repo, applied + already, source_dir=ROOT)
        except Exception as exc:
            print(f"  [cleanup-warn] source cleanup raised: {exc}")
    elif already:
        try:
            create_source_cleanup_pr(args.source_repo, already, source_dir=ROOT)
        except Exception as exc:
            print(f"  [cleanup-warn] source cleanup raised: {exc}")

    print("\n[apply_cross_repo_patch] Execution completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
