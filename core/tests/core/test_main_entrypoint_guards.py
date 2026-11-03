"""AUD-1.2/1.4 — main entrypoint guard & signal handler regression tests.

Covers:
- production hard-fail when UVICORN_WORKERS > 1 (512 MB Render constraint)
- _handle_sigterm does NOT sys.exit (lets Uvicorn lifespan teardown run)
- local mode enables reload, production disables it
"""

import os
import signal
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Import main.py — it must be importable without starting the server.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _settings_stub(env: str) -> SimpleNamespace:
    """Stub for the fields run_server() reads (settings is frozen at import)."""
    # FIX (final-test ci-fixes): main.run_server() এখন settings.is_local() মেথড ব্যবহার করে
    # (local/dev/development — তিনটাতেই reload=True)। তাই stub-এও সেই কন্ট্রাক্ট রাখতে হবে।
    return SimpleNamespace(
        env=env,
        port=8080,
        host="127.0.0.1",
        sentry_dsn=None,
        is_local=lambda: env in ("local", "dev", "development"),
    )


def test_sigterm_handler_does_not_exit_process():
    """AUD-1.4: the handler must NOT force sys.exit (would bypass lifespan teardown)."""
    import main

    with patch.object(main, "logger") as mock_logger:
        # must not raise SystemExit
        main._handle_sigterm(signal.SIGTERM, None)
        mock_logger.info.assert_called()


def test_run_server_production_rejects_multiple_workers():
    """AUD-1.2: workers > 1 in production exits with a critical error (OOM guard)."""
    import main

    env = {"UVICORN_WORKERS": "4", "PORT": "8080"}
    with patch.dict(os.environ, env, clear=False):
        with (
            patch.object(main, "settings", _settings_stub("production")),
            patch.object(main, "uvicorn") as mock_uv,
        ):
            with pytest.raises(SystemExit) as excinfo:
                main.run_server()
            # fail loudly (non-zero) BEFORE uvicorn.run is ever invoked
            assert excinfo.value.code != 0
            mock_uv.run.assert_not_called()


def test_run_server_production_single_worker_starts_uvicorn():
    import main

    env = {"UVICORN_WORKERS": "1", "PORT": "8080"}
    with patch.dict(os.environ, env, clear=False):
        with (
            patch.object(main, "settings", _settings_stub("production")),
            patch.object(main, "uvicorn") as mock_uv,
        ):
            main.run_server()
            mock_uv.run.assert_called_once()
            kwargs = mock_uv.run.call_args.kwargs
            assert kwargs.get("workers") == 1
            assert kwargs.get("reload") is False


def test_run_server_local_uses_reload():
    import main

    with patch.dict(os.environ, {"PORT": "8080"}, clear=False):
        with (
            patch.object(main, "settings", _settings_stub("local")),
            patch.object(main, "uvicorn") as mock_uv,
        ):
            main.run_server()
            mock_uv.run.assert_called_once()
            kwargs = mock_uv.run.call_args.kwargs
            assert kwargs.get("reload") is True


def test_sigterm_env_flag_set():
    """The handler sets UVICORN_SHUTDOWN_REQUESTED so loops can wind down."""
    import main

    os.environ.pop("UVICORN_SHUTDOWN_REQUESTED", None)
    with patch.object(main, "logger"):
        main._handle_sigterm(signal.SIGINT, None)
    assert os.environ.get("UVICORN_SHUTDOWN_REQUESTED") == "1"
