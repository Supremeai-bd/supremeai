import os
import subprocess
import sys
import textwrap


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True,
    )


def test_docs_visible_in_local():
    code = textwrap.dedent(
        """
        import os
        os.environ["env"] = "local"
        os.environ["openrouter_api_key"] = "sk"
        os.environ["gemini_api_key"] = "sk"
        os.environ["sentry_dsn"] = "https://sentry.io/123"
        import core.app as app_mod
        from fastapi.testclient import TestClient
        client = TestClient(app_mod.app)
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        """
    )
    result = _run(code)
    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_disabled_in_production():
    code = textwrap.dedent(
        """
        import os
        os.environ["env"] = "production"
        os.environ["debug"] = "false"
        os.environ["openrouter_api_key"] = "sk"
        os.environ["gemini_api_key"] = "sk"
        os.environ["sentry_dsn"] = "https://sentry.io/123"
        import core.app as app_mod
        from fastapi.testclient import TestClient
        client = TestClient(app_mod.app)
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        """
    )
    result = _run(code)
    assert result.returncode == 0, result.stdout + result.stderr
