# tests/test_apply_cross_repo_patch.py
# বাংলা মন্তব্য: apply_cross_repo_patch.py-এর ক্রস-রেপো প্যাচ ভ্যালিডেশন ও অ্যাপ্লিকেশন লজিকের পূর্ণ ইউনিট টেস্ট

import subprocess
from pathlib import Path
from scripts.ci.apply_cross_repo_patch import (
    is_loop_prevented,
    find_patches,
    validate_patch,
    verify_patch_apply,
    apply_patch,
    get_patch_targets,
    is_already_applied,
    create_source_cleanup_pr,
)


def test_is_loop_prevented():
    # বাংলা মন্তব্য: বট অ্যাক্টরে লুপ গার্ড ট্রু দেবে
    assert is_loop_prevented("github-actions[bot]") is True
    assert is_loop_prevented("dependabot[bot]") is True
    assert is_loop_prevented("renovate[bot]") is True
    # সাধারণ এজেন্ট বা হিউম্যানে ফলস দেবে
    assert is_loop_prevented("supremeai-admin") is False
    assert is_loop_prevented("coder-1") is False


def test_find_patches(tmp_path: Path):
    patch_dir = tmp_path / ".patches" / "public"
    patch_dir.mkdir(parents=True)

    # ফাঁকা ডিরেক্টরিতে কিছু নেই
    assert find_patches(patch_dir) == []

    # বিভিন্ন ফাইল তৈরি
    (patch_dir / "01-feature.patch").write_text("diff --git a/test b/test", encoding="utf-8")
    (patch_dir / "02-fix.diff").write_text("diff --git a/fix b/fix", encoding="utf-8")
    (patch_dir / "notes.txt").write_text("some notes", encoding="utf-8")

    patches = find_patches(patch_dir)
    assert len(patches) == 2
    names = [p.name for p in patches]
    assert names == ["01-feature.patch", "02-fix.diff"]


def test_validate_patch(tmp_path: Path):
    # অস্তিত্বহীন ফাইল
    ok, msg = validate_patch(tmp_path / "nonexistent.patch")
    assert ok is False
    assert "not found" in msg.lower()

    # খালি ফাইল
    empty_p = tmp_path / "empty.patch"
    empty_p.write_text("", encoding="utf-8")
    ok, msg = validate_patch(empty_p)
    assert ok is False
    assert "empty" in msg.lower()

    # অবৈধ ফরম্যাট
    invalid_p = tmp_path / "invalid.patch"
    invalid_p.write_text("hello world without git diff markers", encoding="utf-8")
    ok, msg = validate_patch(invalid_p)
    assert ok is False
    assert "invalid patch format" in msg.lower()

    # বৈধ ফরম্যাট
    valid_p = tmp_path / "valid.patch"
    valid_p.write_text("diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new", encoding="utf-8")
    ok, msg = validate_patch(valid_p)
    assert ok is True
    assert msg == "Valid"


def test_patch_apply_with_git_repo(tmp_path: Path):
    # বাংলা মন্তব্য: টেস্টের জন্য একটি লোকাল git রিপো ইনিশিয়ালাইজ করা
    target_repo = tmp_path / "target_repo"
    target_repo.mkdir()

    subprocess.run(["git", "init"], cwd=target_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=target_repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@supremeai.live"], cwd=target_repo, check=True)

    test_file = target_repo / "greeting.txt"
    test_file.write_text("Hello World\n", encoding="utf-8")
    subprocess.run(["git", "add", "greeting.txt"], cwd=target_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=target_repo, check=True)

    # বৈধ প্যাচ তৈরি (Hello World -> Hello SupremeAI)
    patch_file = tmp_path / "greeting.patch"
    patch_content = (
        "diff --git a/greeting.txt b/greeting.txt\n"
        "--- a/greeting.txt\n"
        "+++ b/greeting.txt\n"
        "@@ -1 +1 @@\n"
        "-Hello World\n"
        "+Hello SupremeAI\n"
    )
    patch_file.write_text(patch_content, encoding="utf-8")

    # Dry-run check
    can_apply, check_msg = verify_patch_apply(target_repo, patch_file)
    assert can_apply is True

    # Real apply
    applied, apply_msg = apply_patch(target_repo, patch_file)
    assert applied is True
    assert test_file.read_text(encoding="utf-8") == "Hello SupremeAI\n"

    # পুনরায় একই প্যাচ দিলে কনফ্লিক্ট ধরা পড়বে
    can_apply_again, conflict_msg = verify_patch_apply(target_repo, patch_file)
    assert can_apply_again is False

    # বাংলা মন্তব্য: numstat থেকে টার্গেট ফাইলের নাম নিখুঁতভাবে পাওয়া
    targets = get_patch_targets(patch_file)
    assert targets == ["greeting.txt"]


def test_is_already_applied(tmp_path: Path):
    """বাংলা মন্তব্য: প্যাচ আগে থেকেই apply করা থাকলে reverse-check True দেবে।"""
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    f = repo / "a.txt"
    f.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=repo, check=True, capture_output=True)

    patch = tmp_path / "p.patch"
    patch.write_text(
        "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-one\n+two\n",
        encoding="utf-8",
    )

    # not applied yet → False
    assert is_already_applied(repo, patch) is False
    # apply → True
    subprocess.run(["git", "apply", str(patch)], cwd=repo, check=True, capture_output=True)
    assert is_already_applied(repo, patch) is True


def test_create_source_cleanup_pr_no_token(tmp_path: Path, monkeypatch):
    """GH_TOKEN না থাকলে cleanup False ফেরত দেবে (fail-visible, silent skip নয়)।"""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    ok = create_source_cleanup_pr(
        "Supremeai-bd/supremeai",
        [tmp_path / "missing.patch"],
        source_dir=tmp_path,
    )
    assert ok is False
