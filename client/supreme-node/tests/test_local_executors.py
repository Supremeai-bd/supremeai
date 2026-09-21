"""
Tests for local_executors.py — REAL subprocess execution (no mocks).
MESH-3 #941 — Phase A

These tests actually invoke subprocesses (bash, pytest, git) to verify the
executor layer. They run in tmpdirs to avoid touching the host workspace.

env1.txt directive: "No Fake Mocking" — executors are 100% real here.
Only the WebSocket transport (in test_daemon.py) is mocked — that's the
CLIENT-side transport boundary, explicitly allowed.
"""
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# Make supreme-node importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from local_executors import (  # noqa: E402
    LocalExecutor,
    ExecResult,
    TestResult,
    GitResult,
    parse_pytest_summary,
    dispatch_task,
    VALID_TASK_TYPES,
)


def _async_run(coro):
    """Helper — run a coroutine to completion synchronously."""
    return asyncio.new_event_loop().run_until_complete(coro)


class TestParsePytestSummary(unittest.TestCase):
    """pytest output parser — pure function tests।"""

    def test_all_passed(self):
        raw = "===== 3 passed in 1.23s ====="
        out = parse_pytest_summary(raw)
        self.assertEqual(out["passed"], 3)
        self.assertEqual(out["failed"], 0)
        self.assertEqual(out["total"], 3)

    def test_mixed_results(self):
        raw = "===== 1 failed, 2 passed, 1 skipped, 3 errors in 2.5s ====="
        out = parse_pytest_summary(raw)
        self.assertEqual(out["passed"], 2)
        self.assertEqual(out["failed"], 1)
        self.assertEqual(out["skipped"], 1)
        self.assertEqual(out["errors"], 3)
        self.assertEqual(out["total"], 7)

    def test_no_summary_line(self):
        raw = "garbage output, no summary here"
        out = parse_pytest_summary(raw)
        self.assertEqual(out["passed"], 0)
        self.assertEqual(out["total"], 0)

    def test_xfailed_counts_as_skipped(self):
        raw = "===== 1 passed, 1 xfailed in 0.5s ====="
        out = parse_pytest_summary(raw)
        self.assertEqual(out["passed"], 1)
        self.assertEqual(out["skipped"], 1)


class TestRunBash(unittest.TestCase):
    """run_bash — REAL asyncio.subprocess execution।"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.exec = LocalExecutor(workspace_dir=self.tmpdir)

    def test_echo_hello(self):
        r = _async_run(self.exec.run_bash("echo hello"))
        self.assertIsInstance(r, ExecResult)
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.stdout.strip(), "hello")
        self.assertEqual(r.stderr, "")
        self.assertFalse(r.timed_out)
        self.assertTrue(r.ok)
        self.assertGreater(r.duration_seconds, 0)

    def test_multi_line_output(self):
        r = _async_run(self.exec.run_bash("printf 'line1\\nline2\\nline3\\n'"))
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.stdout, "line1\nline2\nline3\n")

    def test_exit_code_nonzero(self):
        r = _async_run(self.exec.run_bash("exit 42"))
        self.assertEqual(r.exit_code, 42)
        self.assertFalse(r.ok)

    def test_stderr_captured(self):
        r = _async_run(self.exec.run_bash("echo err >&2; exit 1"))
        self.assertEqual(r.exit_code, 1)
        self.assertEqual(r.stderr.strip(), "err")

    def test_pipe_works(self):
        # pipe through bash -c — verifies shell semantics
        r = _async_run(self.exec.run_bash("echo 'a b c' | wc -w"))
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.stdout.strip(), "3")

    def test_timeout_kills_process(self):
        # sleep 10s but timeout=0.3s — should kill + report timed_out
        r = _async_run(self.exec.run_bash("sleep 10", timeout=0.3))
        self.assertTrue(r.timed_out)
        self.assertFalse(r.ok)

    def test_cwd_is_workspace(self):
        # touch a file in workspace, then list it
        _async_run(self.exec.run_bash("touch marker.txt"))
        r = _async_run(self.exec.run_bash("ls marker.txt"))
        self.assertEqual(r.exit_code, 0, msg=f"ls failed: {r.stderr}")


class TestRunPytest(unittest.TestCase):
    """run_pytest — REAL pytest subprocess।"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        # write a tiny test file
        self.test_file = os.path.join(self.tmpdir, "test_sample.py")
        with open(self.test_file, "w") as f:
            f.write(
                "def test_pass_one():\n"
                "    assert 1 + 1 == 2\n"
                "\n"
                "def test_pass_two():\n"
                "    assert 'a' + 'b' == 'ab'\n"
            )
        self.exec = LocalExecutor(workspace_dir=self.tmpdir)

    def test_runs_and_parses(self):
        r = _async_run(self.exec.run_pytest(self.test_file))
        self.assertIsInstance(r, TestResult)
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.passed, 2)
        self.assertEqual(r.failed, 0)
        self.assertEqual(r.total, 2)
        self.assertTrue(r.ok)
        self.assertIn("test_pass_one", r.raw_output)

    def test_failed_test_detected(self):
        with open(self.test_file, "w") as f:
            f.write("def test_fail():\n    assert False\n")
        r = _async_run(self.exec.run_pytest(self.test_file))
        self.assertEqual(r.failed, 1)
        self.assertEqual(r.exit_code, 1)
        self.assertFalse(r.ok)


class TestRunOllama(unittest.TestCase):
    """run_ollama — local Ollama call। Skip if Ollama না চলছে।"""

    def setUp(self):
        self.exec = LocalExecutor(ollama_url="http://localhost:11434")

    def _ollama_running(self) -> bool:
        import socket
        try:
            with socket.create_connection(("localhost", 11434), timeout=0.5):
                return True
        except OSError:
            return False

    def test_ollama_call_or_skip(self):
        if not self._ollama_running():
            self.skipTest("Ollama চলছে না localhost:11434 — skip")
        try:
            text = _async_run(self.exec.run_ollama("Say hi", model="llama3.2",
                                                   timeout=60.0))
            self.assertIsInstance(text, str)
        except Exception as e:
            # HTTP error ok — model না থাকলে 404 আসতে পারে
            import httpx
            if not isinstance(e, httpx.HTTPError):
                raise

    def test_connection_error_on_unreachable(self):
        # Point to port nobody listens on
        bad_exec = LocalExecutor(ollama_url="http://localhost:1")
        import httpx
        with self.assertRaises(httpx.HTTPError):
            _async_run(bad_exec.run_ollama("hi", timeout=0.5))


class TestGitCommitPush(unittest.TestCase):
    """git_commit_push — REAL git subprocess।"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        # init a fresh git repo with identity set (no global git config assumed)
        subprocess.run(["git", "init", "-q"], cwd=self.tmpdir, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@supremeai.local"],
            cwd=self.tmpdir, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "supreme-node-test"],
            cwd=self.tmpdir, check=True,
        )
        # also disable commit signing (sandbox-এ GPG নেই)
        subprocess.run(
            ["git", "config", "commit.gpgsign", "false"],
            cwd=self.tmpdir, check=True,
        )
        # initial commit on main so we have a base
        with open(os.path.join(self.tmpdir, "README.md"), "w") as f:
            f.write("# test repo\n")
        subprocess.run(["git", "add", "."], cwd=self.tmpdir, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "initial commit"],
            cwd=self.tmpdir, check=True,
        )
        self.exec = LocalExecutor(workspace_dir=self.tmpdir)

    def test_creates_branch_commits_push_disabled(self):
        # push disabled (no remote configured) — just commit locally.
        # Modify the file so there's something to commit.
        with open(os.path.join(self.tmpdir, "README.md"), "a") as f:
            f.write("\nnew line from test_creates_branch_commits_push_disabled\n")
        r = _async_run(
            self.exec.git_commit_push(
                branch="feat/test-1",
                files=["README.md"],
                msg="test commit by supreme-node",
                push=False,
            )
        )
        self.assertIsInstance(r, GitResult)
        self.assertEqual(r.branch, "feat/test-1")
        self.assertTrue(r.commit_sha, msg=f"no commit sha — msg={r.message}")
        self.assertEqual(len(r.commit_sha), 40)  # SHA-1 length
        self.assertFalse(r.pushed)  # we said push=False
        self.assertGreater(r.files_staged, 0)
        self.assertEqual(r.message, "ok")

        # verify branch actually exists
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.tmpdir, capture_output=True, text=True, check=True,
        )
        self.assertEqual(out.stdout.strip(), "feat/test-1")

    def test_commit_modification(self):
        # modify existing file
        with open(os.path.join(self.tmpdir, "README.md"), "a") as f:
            f.write("\nmore content\n")
        r = _async_run(
            self.exec.git_commit_push(
                branch="main",
                files=["README.md"],
                msg="update readme",
                push=False,
            )
        )
        self.assertTrue(r.commit_sha, msg=r.message)
        self.assertFalse(r.pushed)  # no remote

    def test_unknown_branch_auto_creates(self):
        # First time branch doesn't exist — should create it.
        # Modify file so commit succeeds.
        with open(os.path.join(self.tmpdir, "README.md"), "a") as f:
            f.write("\nnew content for brand new branch\n")
        r = _async_run(
            self.exec.git_commit_push(
                branch="feat/brand-new",
                files=["README.md"],
                msg="brand new",
                push=False,
            )
        )
        self.assertTrue(r.commit_sha, msg=r.message)

    def test_push_no_remote_reports_failure(self):
        # push=True but no remote configured — should report not pushed.
        # First modify + commit locally, then attempt push to fail.
        with open(os.path.join(self.tmpdir, "README.md"), "a") as f:
            f.write("\npush attempt content\n")
        r = _async_run(
            self.exec.git_commit_push(
                branch="feat/test-push",
                files=["README.md"],
                msg="try push",
                push=True,
            )
        )
        # commit should succeed (file modified), push will fail (no remote)
        self.assertTrue(r.commit_sha, msg=f"commit should succeed: {r.message}")
        self.assertFalse(r.pushed)
        self.assertIn("push failed", r.message)


class TestDispatchTask(unittest.TestCase):
    """dispatch_task — task routing।"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.exec = LocalExecutor(workspace_dir=self.tmpdir)

    def test_bash_dispatch(self):
        out = _async_run(dispatch_task(self.exec, {
            "task_id": "t1",
            "type": "bash",
            "payload": {"cmd": "echo dispatched"},
        }))
        self.assertEqual(out["task_id"], "t1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["result"]["stdout"].strip(), "dispatched")

    def test_unknown_type_errors(self):
        out = _async_run(dispatch_task(self.exec, {
            "task_id": "t2",
            "type": "rocket",
            "payload": {},
        }))
        self.assertEqual(out["status"], "error")
        self.assertIn("unknown task type", out["result"]["error"])

    def test_pytest_dispatch_real(self):
        # tiny test file
        test_path = os.path.join(self.tmpdir, "test_dispatch.py")
        with open(test_path, "w") as f:
            f.write("def test_x():\n    assert True\n")
        out = _async_run(dispatch_task(self.exec, {
            "task_id": "t3",
            "type": "pytest",
            "payload": {"test_path": test_path},
        }))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["result"]["passed"], 1)

    def test_valid_task_types_set(self):
        self.assertIn("bash", VALID_TASK_TYPES)
        self.assertIn("pytest", VALID_TASK_TYPES)
        self.assertIn("ollama", VALID_TASK_TYPES)
        self.assertIn("git_push", VALID_TASK_TYPES)


if __name__ == "__main__":
    unittest.main()
