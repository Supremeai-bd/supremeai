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
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def is_loop_prevented(actor: str | None = None) -> bool:
    """বাংলা মন্তব্য: dependency-bot নীতি অপরিবর্তিত; canonical sync bot-কে আটকাব না।"""
    current_actor = actor or os.getenv("GITHUB_ACTOR", "")
    blocked_actors = {
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
    """বাংলা মন্তব্য: clean target main-এ reverse-check সফল হওয়ার পরেই source cleanup PR।
    শুধু target PR খোলা input মুছে ফেলার প্রমাণ নয়।

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

    slug = sync_branch_name([src / r for r in existing]).removeprefix("sync/patch-")
    branch_name = f"sync/consume-{slug}"
    state = sync_pr_state(src, source_repo, branch_name, legacy_branch=f"sync/consume-{'-'.join(Path(r).stem for r in existing[:3])[:30]}")
    if state != "new":
        return state == "open"

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
        "Target main-এ content যাচাইয়ের পরে অপসারণ:\n"
        + "\n".join(f"- {r}" for r in existing)
    )
    try:
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=src, check=True)
        subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=src, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"  [cleanup-error] git commit/push failed: {exc}")
        return False

    pr_body = (
        "## Rule #10 loop-stop — consume cross-repo patch inputs\n\n"
        "Target main-এ patch-এর content reverse-check দিয়ে যাচাই হয়েছে। "
        "This PR deletes the input patch file(s) from `.patches/` so future pushes "
        "পুনরায় sync না হয়।\n\n"
        "### Removed\n"
        + "\n".join(f"- `{r}`" for r in existing)
        + "\n\n> Loop-guard: target main-এ content থাকা যাচাই ছাড়া source input মুছবেন না।"
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


def sync_branch_name(patches: list[Path]) -> str:
    """বাংলা মন্তব্য: ফাইলের নাম ও bytes দিয়ে branch; truncated slug collision নয়।"""
    digest = hashlib.sha256()
    for patch in sorted(patches, key=lambda p: p.name):
        for part in (patch.name.encode("utf-8"), patch.read_bytes()):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return f"sync/patch-{digest.hexdigest()[:24]}"


def sync_pr_state(work_dir: Path, repo: str, branch_name: str, *, legacy_branch: str | None = None, query_state: str = "all") -> str:
    """বাংলা মন্তব্য: target ও cleanup উভয়ের এক lookup; ব্যর্থতায় কোনো git write নয়।"""
    try:
        prs = json.loads(subprocess.check_output(
            ["gh", "pr", "list", "--repo", repo, "--head", branch_name,
             "--state", query_state, "--json", "number,state"],
            cwd=work_dir, text=True,
        ))
        if not isinstance(prs, list):
            raise ValueError("PR lookup did not return a list")
        if prs:
            if len(prs) == 1 and prs[0].get("state") == "OPEN":
                print(f"  [reuse] PR #{prs[0]['number']} already open; no push needed.")
                return "open"
            print("  [blocked] Prior PR is not uniquely open; review before reapplying this patch.")
            return "blocked"
    except (subprocess.CalledProcessError, OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        print(f"  [error] PR lookup failed; refusing duplicate submission: {exc}")
        return "blocked"

    # বাংলা মন্তব্য: পুরনো slug-branch-এর PR খোলা থাকলে দ্বিতীয় hash-branch খুলব না।
    if legacy_branch and sync_pr_state(work_dir, repo, legacy_branch, query_state="open") != "new":
        print("  [blocked] Legacy branch has an open/unknown PR; resolve it before changing branch format.")
        return "blocked"
    return "new"


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

    # বাংলা মন্তব্য: একই content-এর open PR থাকলে কোনো branch/commit/push নয়।
    # lookup ব্যর্থ বা পুরনো PR বন্ধ/merged অথচ content অনুপস্থিত হলে মানুষের যাচাই লাগবে।
    branch_name = sync_branch_name(applied_patches)
    state = sync_pr_state(target_dir, target_repo, branch_name, legacy_branch=f"sync/patch-{'-'.join(p.stem for p in applied_patches[:3])[:30]}")
    if state != "new":
        return state == "open"

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

    print(f"  [git] Configuring bot identity and checkout branch '{branch_name}'...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=target_dir, check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=target_dir, check=True)
    subprocess.run(["git", "checkout", "-B", branch_name], cwd=target_dir, check=True)

    print(f"  [git] Staging {len(files_to_stage)} targeted file(s) strictly from patches...")
    subprocess.run(["git", "add", "--"] + sorted(files_to_stage), cwd=target_dir, check=True)

    commit_msg = f"chore(sync): cross-repo patch sync from {source_repo}\n\nApplied patches:\n" + "\n".join(f"- {p}" for p in patch_names)
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=target_dir, check=True)
    subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=target_dir, check=True)

    pr_body = (
        f"## Automated Cross-Repo Patch Synchronization\n\n"
        f"- **Source Repo:** `{source_repo}` (`{source_ref}`)\n"
        f"- **Applied Patches:**\n"
        + "\n".join(f"  - `{p}`" for p in patch_names)
        + "\n\n### বাংলা বিবরণ\n"
        f"সোর্স রিপোজিটরি `{source_repo}`-এর পরিবর্তনের পরিপ্রেক্ষিতে এই প্যাচটি স্বয়ংক্রিয়ভাবে প্রয়োগ করে PR তৈরি করা হয়েছে।\n\n"
        f"> 🛡️ একই content-এর PR reuse হয়; source cleanup শুধু target main-এ reverse-check-এর পরে।\n"
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

    if is_loop_prevented():
        print("[apply_cross_repo_patch] Dependency-bot actor skipped by policy.")
        return 0

    patch_dir = Path(args.patch_dir).resolve()
    target_dir = Path(args.target_dir).resolve()
    if not target_dir.exists():
        print(f"Error: Target directory does not exist: {target_dir}")
        return 1
    patches = find_patches(patch_dir)
    if not patches:
        print(f"[apply_cross_repo_patch] No patch files found in {patch_dir}.")
        return 0

    # বাংলা মন্তব্য: local dirty work merge-এর প্রমাণ নয়, অন্যের ফাইল sync-এ যাবে না।
    # target clone অবশ্যই main-এ থাকবে; apply হওয়ার আগেই এই check করতে হবে।
    try:
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=target_dir, text=True)
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=target_dir, text=True).strip()
        if dirty.strip() or branch != "main":
            print("[blocked] Target must be a clean main checkout before patch processing.")
            return 1
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[error] Target checkout verification failed: {exc}")
        return 1

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
            print(f"  [already-landed] {p.name}: reverse-check OK on clean main.")
            already.append(p)
        else:
            print(f"Conflict error for {p.name}: {check_msg}")
            return 1

    if args.dry_run or not (args.apply or args.create_pr):
        print("[read-only] Validation completed; no files/PRs changed.")
        return 0

    for p in pending:
        success, msg = apply_patch(target_dir, p)
        if not success:
            print(f"Failed to apply {p.name}: {msg}")
            return 1

    if args.create_pr and pending:
        if not create_sync_pr(
            target_dir=target_dir, target_repo=args.target_repo,
            source_repo=args.source_repo, applied_patches=pending, source_ref=args.source_ref,
        ):
            return 1

    # বাংলা মন্তব্য: এই run-এ নতুন apply করা patch এখনো merged নয়; শুধু পূর্বপ্রমাণিত
    # already তালিকাই consume হবে। --apply/validation কখনো GitHub-এ mutation করবে না।
    if args.create_pr and already:
        try:
            if not create_source_cleanup_pr(args.source_repo, already, source_dir=ROOT):
                print("[cleanup-warn] Source cleanup incomplete; inputs retained for retry.")
        except Exception as exc:
            print(f"[cleanup-warn] Source cleanup failed: {exc}")
    print("[apply_cross_repo_patch] Execution completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
