# বাংলা মন্তব্য: শুধু অস্থায়ী git repo ও mocked gh দিয়ে Rule 10 lifecycle যাচাই; নেটওয়ার্ক/push নয়।
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(os.environ.get("CROSS_REPO_SYNC_SCRIPT", Path(__file__).with_name("apply_cross_repo_patch.py")))
SPEC = importlib.util.spec_from_file_location("sync_under_test", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)
CREATE_SYNC_PR = sync.create_sync_pr
CREATE_CLEANUP_PR = sync.create_source_cleanup_pr


class TestSyncLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "target"
        self.target.mkdir()
        self.source = self.root / "source"
        self.patch_dir = self.source / ".patches" / "public"
        self.patch_dir.mkdir(parents=True)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Local Test")
        self.git("config", "user.email", "local-test@example.invalid")
        (self.target / "hello.txt").write_text("before\n", encoding="utf-8")
        self.git("add", "hello.txt")
        self.git("commit", "-m", "initial")
        self.patch_file = self.patch_dir / "change.patch"
        self.patch_file.write_text(
            "diff --git a/hello.txt b/hello.txt\n--- a/hello.txt\n+++ b/hello.txt\n"
            "@@ -1 +1 @@\n-before\n+after\n",
            encoding="utf-8",
        )
        for name, value in [("ROOT", self.source), ("create_sync_pr", None), ("create_source_cleanup_pr", None)]:
            stub = patch.object(sync, name, value, create=True) if value is not None else patch.object(sync, name, return_value=True, create=True)
            mock = stub.start()
            self.addCleanup(stub.stop)
            if name == "create_sync_pr":
                self.submit = mock
            elif name == "create_source_cleanup_pr":
                self.cleanup = mock

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.target, stderr=subprocess.STDOUT, text=True)

    def cli(self, *flags, actor="human"):
        argv = [str(SCRIPT), "--patch-dir", str(self.patch_dir), "--target-dir", str(self.target), "--source-repo", "Supremeai-bd/supremeai"]
        with patch.object(sys, "argv", argv + list(flags)), patch.dict(os.environ, {"GITHUB_ACTOR": actor}), contextlib.redirect_stdout(io.StringIO()):
            return sync.main()

    def land_patch(self):
        self.git("apply", str(self.patch_file))
        self.git("add", "hello.txt")
        self.git("commit", "-m", "land patch")

    def test_actions_bot_processes_pending_patch(self):
        self.assertEqual(self.cli("--create-pr", actor="github-actions[bot]"), 0)
        self.assertEqual((self.target / "hello.txt").read_text(), "after\n")
        self.submit.assert_called_once()

    def test_dependency_bot_policy_is_unchanged(self):
        self.assertEqual(self.cli("--create-pr", actor="dependabot[bot]"), 0)
        self.assertEqual((self.target / "hello.txt").read_text(), "before\n")
        self.submit.assert_not_called()
        self.cleanup.assert_not_called()

    def test_new_target_pr_never_consumes_source_patch(self):
        self.assertEqual(self.cli("--create-pr"), 0)
        self.submit.assert_called_once()
        self.cleanup.assert_not_called()
        self.assertTrue(self.patch_file.exists())

    def test_already_landed_patch_only_requests_cleanup(self):
        self.land_patch()
        self.assertEqual(self.cli("--create-pr", actor="github-actions[bot]"), 0)
        self.submit.assert_not_called()
        self.cleanup.assert_called_once()

    def test_already_landed_dry_run_never_writes(self):
        self.land_patch()
        self.assertEqual(self.cli("--dry-run"), 0)
        self.submit.assert_not_called()
        self.cleanup.assert_not_called()

    def test_validation_only_never_requests_cleanup(self):
        self.land_patch()
        self.assertEqual(self.cli(), 0)
        self.submit.assert_not_called()
        self.cleanup.assert_not_called()

    def test_apply_only_never_requests_cleanup(self):
        self.land_patch()
        self.assertEqual(self.cli("--apply"), 0)
        self.cleanup.assert_not_called()

    def test_conflict_fails_without_writes(self):
        (self.target / "hello.txt").write_text("unrelated\n")
        self.git("add", "hello.txt")
        self.git("commit", "-m", "conflict")
        self.assertEqual(self.cli("--create-pr"), 1)
        self.submit.assert_not_called()
        self.cleanup.assert_not_called()

    def test_dirty_target_cannot_be_taken_as_merge_proof(self):
        self.git("apply", str(self.patch_file))
        self.assertEqual(self.cli("--create-pr"), 1)
        self.submit.assert_not_called()
        self.cleanup.assert_not_called()

    def test_non_main_branch_is_not_merge_proof(self):
        self.land_patch()
        self.git("checkout", "-b", "unmerged-work")
        self.assertEqual(self.cli("--create-pr"), 1)
        self.submit.assert_not_called()
        self.cleanup.assert_not_called()

    def test_cleanup_failure_never_deletes_input_in_the_caller(self):
        self.land_patch()
        self.cleanup.return_value = False
        self.assertEqual(self.cli("--create-pr"), 0)
        self.assertTrue(self.patch_file.exists())
        self.submit.assert_not_called()

    def test_unrelated_dirty_file_cannot_leak_into_sync(self):
        (self.target / "unrelated.txt").write_text("private local work\n")
        self.assertEqual(self.cli("--create-pr"), 1)
        self.assertEqual((self.target / "hello.txt").read_text(), "before\n")
        self.submit.assert_not_called()
        self.cleanup.assert_not_called()

    def test_mixed_batch_only_consumes_landed_sibling(self):
        self.land_patch()
        pending = self.patch_dir / "second.patch"
        pending.write_text("diff --git a/new.txt b/new.txt\nnew file mode 100644\n--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+new\n")
        self.assertEqual(self.cli("--create-pr"), 0)
        self.submit.assert_called_once()
        self.cleanup.assert_called_once_with("Supremeai-bd/supremeai", [self.patch_file], source_dir=self.source)

    def test_failed_target_pr_does_not_consume_pending_patch(self):
        self.submit.return_value = False
        self.assertEqual(self.cli("--create-pr"), 1)
        self.cleanup.assert_not_called()
        self.assertTrue(self.patch_file.exists())

    def test_packager_preserves_crlf_and_final_blank_context(self):
        path = Path(__file__).with_name('create_cross_repo_patch.py')
        spec = importlib.util.spec_from_file_location('packager_under_test', path)
        packager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packager)
        raw = b'diff --git a/crlf.txt b/crlf.txt\n--- a/crlf.txt\n+++ b/crlf.txt\n@@ -1,3 +1,3 @@\n one\r\n-two\r\n+TWO\r\n \r\n'
        original = self.root / 'original.diff'
        original.write_bytes(raw)
        (self.target / 'crlf.txt').write_bytes(b'one\r\ntwo\r\n\r\n')
        argv = [str(path), '--target', 'private', '--slug', 'crlf', '--diff-file', str(original)]
        with patch.object(packager, 'ROOT', self.source), patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(packager.main(), 0)
        output = self.source / '.patches/private/crlf.patch'
        self.assertEqual(output.read_bytes(), raw)
        self.git('apply', '--check', str(output))

    def test_packager_preserves_git_diff_input_bytes(self):
        path = Path(__file__).with_name('create_cross_repo_patch.py')
        spec = importlib.util.spec_from_file_location('packager_staged_under_test', path)
        packager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packager)
        (self.target / 'crlf.txt').write_bytes(b'one\r\ntwo\r\n')
        self.git('add', 'crlf.txt')
        self.git('commit', '-m', 'CRLF fixture')
        (self.target / 'crlf.txt').write_bytes(b'one\r\nTWO\r\n')
        self.git('add', 'crlf.txt')
        raw = subprocess.check_output(['git', 'diff', '--cached'], cwd=self.target)
        argv = [str(path), '--target', 'private', '--slug', 'staged', '--from-staged']
        with patch.object(packager, 'ROOT', self.target), patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(packager.main(), 0)
        self.assertEqual((self.target / '.patches/private/staged.patch').read_bytes(), raw)

    def test_branch_identity_changes_with_patch_bytes(self):
        first = sync.sync_branch_name([self.patch_file])
        self.patch_file.write_text(self.patch_file.read_text() + "\n")
        self.assertNotEqual(first, sync.sync_branch_name([self.patch_file]))

    def test_branch_identity_changes_with_same_prefix_filename(self):
        prefix = "same-truncated-prefix-" * 3
        first = self.patch_dir / (prefix + "a.patch")
        other = self.patch_dir / (prefix + "b.patch")
        first.write_bytes(self.patch_file.read_bytes())
        other.write_bytes(self.patch_file.read_bytes())
        self.assertNotEqual(sync.sync_branch_name([first]), sync.sync_branch_name([other]))

    def test_branch_identity_is_order_independent(self):
        other = self.patch_dir / "other.patch"
        other.write_text("other content")
        self.assertEqual(sync.sync_branch_name([self.patch_file, other]), sync.sync_branch_name([other, self.patch_file]))

    def test_existing_cleanup_pr_is_reused_before_git_writes(self):
        with patch.dict(os.environ, {"GH_TOKEN": "unit"}), patch.object(sync.subprocess, "check_output", return_value=json.dumps([{"number": 19, "state": "OPEN"}])), patch.object(sync.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(CREATE_CLEANUP_PR("Supremeai-bd/source", [self.patch_file], source_dir=self.source))
        run.assert_not_called()

    def test_cleanup_lookup_failure_never_writes(self):
        with patch.dict(os.environ, {"GH_TOKEN": "unit"}), patch.object(sync.subprocess, "check_output", side_effect=subprocess.CalledProcessError(1, "gh")), patch.object(sync.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(CREATE_CLEANUP_PR("Supremeai-bd/source", [self.patch_file], source_dir=self.source))
        run.assert_not_called()
        self.assertTrue(self.patch_file.exists())

    def test_legacy_open_pr_blocks_a_second_branch(self):
        with patch.object(sync.subprocess, "check_output", side_effect=["[]", json.dumps([{"number": 107, "state": "OPEN"}])]), patch.object(sync.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            state = sync.sync_pr_state(self.target, "Supremeai-bd/target", "sync/patch-hash", legacy_branch="sync/patch-old")
        self.assertEqual(state, "blocked")
        run.assert_not_called()

    def run_submit(self, prs=None, lookup_error=None):
        def output(command, **kwargs):
            if command[:3] == ["git", "status", "--porcelain"]:
                return " M hello.txt\n"
            if command[:3] == ["gh", "pr", "list"]:
                if lookup_error:
                    raise lookup_error
                return json.dumps(prs or [])
            raise AssertionError(f"অপ্রত্যাশিত subprocess: {command}")

        with patch.object(sync.subprocess, "check_output", side_effect=output), patch.object(sync.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            ok = CREATE_SYNC_PR(self.target, "Supremeai-bd/target", "Supremeai-bd/source", [self.patch_file])
        return ok, run

    def test_existing_open_pr_is_reused_without_git_writes(self):
        ok, run = self.run_submit([{"number": 17, "state": "OPEN"}])
        self.assertTrue(ok)
        run.assert_not_called()

    def test_closed_pr_requires_review_instead_of_reopening(self):
        ok, run = self.run_submit([{"number": 17, "state": "CLOSED"}])
        self.assertFalse(ok)
        run.assert_not_called()

    def test_previously_merged_but_now_missing_content_requires_review(self):
        ok, run = self.run_submit([{"number": 17, "state": "MERGED"}])
        self.assertFalse(ok)
        run.assert_not_called()

    def test_lookup_failure_does_not_push_or_create_duplicate_pr(self):
        ok, run = self.run_submit(lookup_error=subprocess.CalledProcessError(1, "gh"))
        self.assertFalse(ok)
        run.assert_not_called()

    def test_new_pr_uses_non_forced_push(self):
        ok, run = self.run_submit()
        self.assertTrue(ok)
        commands = [call.args[0] for call in run.call_args_list]
        pushes = [cmd for cmd in commands if cmd[:2] == ["git", "push"]]
        self.assertEqual(len(pushes), 1)
        self.assertNotIn("--force", pushes[0])
        self.assertNotIn("--force-with-lease", pushes[0])
        self.assertTrue(any(cmd[:3] == ["gh", "pr", "create"] for cmd in commands))


if __name__ == "__main__":
    unittest.main()
