"""
Tests for daemon.py — SupremeNodeDaemon।
MESH-3 #941 — Phase A

Mock policy (env1.txt compliance):
- WebSocket transport (websockets.connect) IS MOCKED — that's the client-side
  transport boundary. The SERVER (Tower) is real per directive; the CLIENT's
  internal logic is what we're testing, so mocking its outbound socket is OK.
- httpx HTTP layer IS MOCKED for heartbeat tests (we're testing the daemon's
  *behavior* on receipt of a 200 / 500 / network-error, not the network).
- Executor layer (LocalExecutor) — REAL subprocess (verified separately in
  test_local_executors.py). When the daemon dispatches a "bash" task, the
  actual `echo hello` runs.

Test cases:
  1. send_heartbeat — 200 OK → lease_active parsed correctly
  2. send_heartbeat — 500 error → returns False
  3. send_heartbeat — network error → returns False (no exception)
  4. heartbeat_loop — sends multiple heartbeats at correct interval
  5. reconnect backoff computation (2, 4, 8, ..., 300 cap)
  6. task dispatch — bash task execute + result post back
  7. message routing — "ping" → "pong" reply; "shutdown" → stop event
  8. unknown message type — ignored gracefully
"""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Make supreme-node importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_config(**overrides):
    """Build a minimal valid config dict for tests।"""
    cfg = {
        "node_id": "pc-1-test",
        "node_type": "local_pc",
        "role": "coder",
        "capabilities": ["bash", "pytest", "git_push"],
        "tower_url": "https://tower.example.com",
        "tower_ws_url": "wss://tower.example.com/ws/node",
        "heartbeat_path": "/api/v1/nodes/heartbeat",
        "heartbeat_interval": 60,
        "reconnect_backoff_base": 2,
        "reconnect_backoff_max": 300,
        "ollama_url": "http://localhost:11434",
        "task_timeout_seconds": 30,
        "workspace_dir": tempfile.mkdtemp(),
        "log_level": "INFO",
        "tower_auth_token": "",
    }
    cfg.update(overrides)
    return cfg


class TestHeartbeat(unittest.TestCase):
    """send_heartbeat + heartbeat_loop — httpx mocked।"""

    def setUp(self):
        import daemon as daemon_mod
        self.daemon_mod = daemon_mod
        self.cfg = _make_config(heartbeat_interval=0.05)  # 50ms for fast tests
        self.daemon = daemon_mod.SupremeNodeDaemon(self.cfg)

    def tearDown(self):
        # Clean up tmp workspace dir
        import shutil
        shutil.rmtree(self.cfg["workspace_dir"], ignore_errors=True)

    def _mock_httpx_response(self, status_code=200, json_data=None, text=""):
        """Build a fake httpx.Response object।"""
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = text or json.dumps(json_data or {})
        if json_data is not None:
            resp.json = MagicMock(return_value=json_data)
        else:
            resp.json = MagicMock(side_effect=ValueError("not json"))
        return resp

    def test_send_heartbeat_success_parses_lease(self):
        lease_data = {
            "status": "ok",
            "lease_active": True,
            "lease_expires_at": "2026-01-01T01:10:00Z",
            "assigned_tasks": ["t1", "t2"],
        }
        mock_resp = self._mock_httpx_response(200, lease_data)
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(self.daemon_mod.httpx, "AsyncClient", return_value=mock_client):
            ok = asyncio.run(self.daemon.send_heartbeat())

        self.assertTrue(ok)
        self.assertTrue(self.daemon._lease_active)
        self.assertEqual(self.daemon._lease_expires_at, "2026-01-01T01:10:00Z")

    def test_send_heartbeat_500_returns_false(self):
        mock_resp = self._mock_httpx_response(500, text="server error")
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(self.daemon_mod.httpx, "AsyncClient", return_value=mock_client):
            ok = asyncio.run(self.daemon.send_heartbeat())
        self.assertFalse(ok)

    def test_send_heartbeat_network_error_returns_false(self):
        import httpx
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("no dns"))

        with patch.object(self.daemon_mod.httpx, "AsyncClient", return_value=mock_client):
            ok = asyncio.run(self.daemon.send_heartbeat())
        self.assertFalse(ok)

    def test_send_heartbeat_includes_required_payload_fields(self):
        """Heartbeat POST body-তে node_id, node_type, role, capabilities,
        timestamp, load সব থাকতে হবে per MESH-1 contract।"""
        mock_resp = self._mock_httpx_response(200, {"status": "ok",
                                                    "lease_active": False,
                                                    "lease_expires_at": "",
                                                    "assigned_tasks": []})
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(self.daemon_mod.httpx, "AsyncClient", return_value=mock_client):
            asyncio.run(self.daemon.send_heartbeat())

        # Inspect the call args
        call_args = mock_client.post.call_args
        self.assertIsNotNone(call_args, "post was not called")
        args, kwargs = call_args
        # First positional arg = URL, OR keyword "url"
        url = args[0] if args else kwargs.get("url")
        self.assertEqual(url, "https://tower.example.com/api/v1/nodes/heartbeat")
        body = kwargs.get("json", {})
        for key in ("node_id", "node_type", "role", "capabilities", "timestamp", "load"):
            self.assertIn(key, body, f"missing {key} in heartbeat body")
        self.assertEqual(body["node_id"], "pc-1-test")
        self.assertEqual(body["node_type"], "local_pc")
        self.assertEqual(body["role"], "coder")
        self.assertIn("bash", body["capabilities"])
        # load sub-keys
        for key in ("cpu", "mem", "active_tasks"):
            self.assertIn(key, body["load"], f"missing load.{key}")

    def test_heartbeat_loop_sends_multiple(self):
        """heartbeat_loop প্রতি interval পরপর POST করে — 3 বার হয় কিনা check।"""
        mock_resp = self._mock_httpx_response(200, {"status": "ok",
                                                    "lease_active": True,
                                                    "lease_expires_at": "x",
                                                    "assigned_tasks": []})
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(self.daemon_mod.httpx, "AsyncClient", return_value=mock_client):
            async def _runner():
                task = asyncio.create_task(self.daemon.heartbeat_loop())
                # Let it run for ~180ms (3-4 heartbeats at 50ms interval)
                await asyncio.sleep(0.18)
                self.daemon._stop_event.set()
                await asyncio.wait_for(task, timeout=2.0)
            asyncio.run(_runner())

        # At least 2 heartbeats should have been sent
        self.assertGreaterEqual(mock_client.post.call_count, 2,
                                msg=f"expected >=2 heartbeats, got {mock_client.post.call_count}")


class TestReconnectBackoff(unittest.TestCase):
    """_compute_backoff — exponential 2, 4, 8, ..., 300 cap।"""

    def setUp(self):
        import daemon as daemon_mod
        self.daemon_mod = daemon_mod
        self.cfg = _make_config(reconnect_backoff_base=2,
                                reconnect_backoff_max=300)
        self.daemon = daemon_mod.SupremeNodeDaemon(self.cfg)

    def test_backoff_progression(self):
        # retry 1 = 2, retry 2 = 4, retry 3 = 8, ...
        expected = [2, 4, 8, 16, 32, 64, 128, 256, 300, 300, 300]
        for i, want in enumerate(expected, start=1):
            got = self.daemon._compute_backoff(i)
            self.assertEqual(got, want, f"retry {i}: expected {want}, got {got}")

    def test_backoff_respects_max_override(self):
        cfg = _make_config(reconnect_backoff_base=2, reconnect_backoff_max=10)
        import daemon as daemon_mod
        d = daemon_mod.SupremeNodeDaemon(cfg)
        self.assertEqual(d._compute_backoff(1), 2)
        self.assertEqual(d._compute_backoff(2), 4)
        self.assertEqual(d._compute_backoff(3), 8)
        self.assertEqual(d._compute_backoff(4), 10)  # capped
        self.assertEqual(d._compute_backoff(10), 10)  # still capped


class TestMessageRouting(unittest.TestCase):
    """_handle_message — type-based routing।"""

    def setUp(self):
        import daemon as daemon_mod
        self.daemon_mod = daemon_mod
        self.cfg = _make_config()
        self.daemon = daemon_mod.SupremeNodeDaemon(self.cfg)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.cfg["workspace_dir"], ignore_errors=True)

    def test_ping_replies_pong(self):
        # Mock the WebSocket so we can capture sends
        self.daemon._ws = MagicMock()
        self.daemon._ws.send = AsyncMock()

        asyncio.run(self.daemon._handle_message({"type": "ping"}))

        self.daemon._ws.send.assert_awaited_once()
        sent_raw = self.daemon._ws.send.call_args.args[0]
        sent = json.loads(sent_raw)
        self.assertEqual(sent["type"], "pong")
        self.assertEqual(sent["node_id"], "pc-1-test")
        self.assertIn("timestamp", sent)

    def test_shutdown_sets_stop_event(self):
        self.assertFalse(self.daemon._stop_event.is_set())
        asyncio.run(self.daemon._handle_message({"type": "shutdown"}))
        self.assertTrue(self.daemon._stop_event.is_set())

    def test_task_message_schedules_execution(self):
        """task message → _execute_and_report টাস্ক তৈরি করে।
        We mock _execute_and_report to avoid running actual subprocess in this test."""
        with patch.object(self.daemon, "_execute_and_report",
                          new=AsyncMock()) as mock_exec:
            asyncio.run(self.daemon._handle_message({
                "type": "task",
                "task_id": "abc-123",
                "task_type": "bash",
                "payload": {"cmd": "echo hi"},
            }))
            # The mock was scheduled via asyncio.create_task — wait a tick
            asyncio.run(asyncio.sleep(0.01))
        mock_exec.assert_called_once()
        task_arg = mock_exec.call_args.args[0]
        self.assertEqual(task_arg["task_id"], "abc-123")
        self.assertEqual(task_arg["type"], "bash")

    def test_unknown_type_ignored(self):
        """unknown message type — log only, no exception।"""
        # No ws attached — should not crash
        asyncio.run(self.daemon._handle_message({"type": "alien"}))
        # No exception = pass

    def test_invalid_json_ignored(self):
        """listen_for_tasks — bad JSON skipped, loop continues।"""
        # Mock ws.recv to return bad JSON once then raise ConnectionError (ends loop)
        self.daemon._ws = MagicMock()
        self.daemon._ws.recv = AsyncMock(side_effect=["not json", ConnectionError("closed")])
        # Should not raise
        asyncio.run(self.daemon.listen_for_tasks())


class TestExecuteAndReport(unittest.TestCase):
    """_execute_and_report — সম্পূর্ণ round trip with REAL executor।"""

    def setUp(self):
        import daemon as daemon_mod
        self.daemon_mod = daemon_mod
        self.cfg = _make_config()
        self.daemon = daemon_mod.SupremeNodeDaemon(self.cfg)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.cfg["workspace_dir"], ignore_errors=True)

    def test_bash_task_executes_and_posts_result(self):
        # Mock ws.send — capture the result message
        self.daemon._ws = MagicMock()
        self.daemon._ws.send = AsyncMock()

        task = {
            "task_id": "t-bash-1",
            "type": "bash",
            "payload": {"cmd": "echo hello-from-task"},
        }
        asyncio.run(self.daemon._execute_and_report(task))

        # Result message sent
        self.daemon._ws.send.assert_awaited()
        sent = json.loads(self.daemon._ws.send.call_args.args[0])
        self.assertEqual(sent["type"], "result")
        self.assertEqual(sent["task_id"], "t-bash-1")
        self.assertEqual(sent["status"], "ok")
        self.assertEqual(sent["result"]["stdout"].strip(), "hello-from-task")
        self.assertEqual(sent["node_id"], "pc-1-test")
        self.assertIn("duration_seconds", sent)

    def test_failed_task_reports_error_status(self):
        self.daemon._ws = MagicMock()
        self.daemon._ws.send = AsyncMock()

        task = {
            "task_id": "t-fail",
            "type": "bash",
            "payload": {"cmd": "exit 7"},
        }
        asyncio.run(self.daemon._execute_and_report(task))

        sent = json.loads(self.daemon._ws.send.call_args.args[0])
        self.assertEqual(sent["status"], "error")
        self.assertEqual(sent["result"]["exit_code"], 7)

    def test_unknown_task_type_reports_error(self):
        self.daemon._ws = MagicMock()
        self.daemon._ws.send = AsyncMock()

        task = {
            "task_id": "t-unknown",
            "type": "rocket",
            "payload": {},
        }
        asyncio.run(self.daemon._execute_and_report(task))
        sent = json.loads(self.daemon._ws.send.call_args.args[0])
        self.assertEqual(sent["status"], "error")
        self.assertIn("unknown task type", sent["result"]["error"])

    def test_send_message_no_ws_does_not_crash(self):
        # No ws attached — should silently skip
        self.daemon._ws = None
        asyncio.run(self.daemon._send_message({"type": "result"}))


class TestConnectAndRun(unittest.TestCase):
    """connect() + run(dry_run=True) — daemon entrypoint smoke।"""

    def setUp(self):
        import daemon as daemon_mod
        self.daemon_mod = daemon_mod
        self.cfg = _make_config()
        self.daemon = daemon_mod.SupremeNodeDaemon(self.cfg)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.cfg["workspace_dir"], ignore_errors=True)

    def test_dry_run_returns_zero_on_heartbeat_success(self):
        """run(dry_run=True) — একবার heartbeat + exit code 0।"""
        lease_data = {
            "status": "ok",
            "lease_active": True,
            "lease_expires_at": "2026-01-01T01:10:00Z",
            "assigned_tasks": [],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=lease_data)
        mock_resp.text = json.dumps(lease_data)
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(self.daemon_mod.httpx, "AsyncClient",
                          return_value=mock_client):
            rc = asyncio.run(self.daemon.run(dry_run=True))
        self.assertEqual(rc, 0)

    def test_dry_run_returns_one_on_heartbeat_failure(self):
        """Heartbeat 500 হলে dry-run returns 1।"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "fail"
        mock_resp.json = MagicMock(side_effect=ValueError())
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch.object(self.daemon_mod.httpx, "AsyncClient",
                          return_value=mock_client):
            rc = asyncio.run(self.daemon.run(dry_run=True))
        self.assertEqual(rc, 1)

    def test_connect_calls_websockets_connect(self):
        """connect() — _ws_connect called with correct URL + headers।"""
        fake_ws = MagicMock()
        fake_ws.close = AsyncMock()
        with patch.object(self.daemon_mod, "_ws_connect",
                          new=AsyncMock(return_value=fake_ws)) as mock_ws:
            asyncio.run(self.daemon.connect())
            asyncio.run(self.daemon._close_ws())
        mock_ws.assert_awaited_once()
        call_kwargs = mock_ws.call_args.kwargs
        # First positional = URL
        url = mock_ws.call_args.args[0]
        self.assertEqual(url, self.cfg["tower_ws_url"])
        self.assertEqual(call_kwargs.get("ping_interval"), 60)


class TestSignalHandling(unittest.TestCase):
    """_handle_signal — SIGTERM/SIGINT sets stop event + cancels tasks।"""

    def setUp(self):
        import daemon as daemon_mod
        self.daemon_mod = daemon_mod
        self.cfg = _make_config()
        self.daemon = daemon_mod.SupremeNodeDaemon(self.cfg)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.cfg["workspace_dir"], ignore_errors=True)

    def test_handle_signal_sets_stop_event(self):
        import signal
        self.assertFalse(self.daemon._stop_event.is_set())
        self.daemon._handle_signal(signal.SIGTERM)
        self.assertTrue(self.daemon._stop_event.is_set())

    def test_handle_signal_cancels_pending_tasks(self):
        import signal
        # Create a fake task
        async def _long():
            try:
                await asyncio.sleep(1000)
            except asyncio.CancelledError:
                pass

        async def _runner():
            t = asyncio.create_task(_long())
            self.daemon._tasks = {t}
            self.daemon._handle_signal(signal.SIGINT)
            # wait briefly for cancellation
            await asyncio.sleep(0.05)
            return t

        t = asyncio.run(_runner())
        self.assertTrue(t.cancelled() or t.done())


if __name__ == "__main__":
    unittest.main()
