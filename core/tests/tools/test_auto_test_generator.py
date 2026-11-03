from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.code.auto_test_generator import (
    AutoTestGenerator,
    TestGenRequest,
    TestGenResponse,
    _detect_framework,
    _detect_stack,
    _extract_python_symbols,
    _get_test_file_path,
    router,
)


@pytest.fixture
def generator():
    return AutoTestGenerator()


@pytest.mark.parametrize(
    "file_path,source_code,expected",
    [
        ("foo.py", "", "python"),
        ("foo.ts", "", "typescript"),
        ("foo.tsx", "", "typescript"),
        ("foo.js", "", "javascript"),
        ("foo.jsx", "", "javascript"),
        ("foo.dart", "", "dart"),
        ("foo.java", "", "java"),
        ("foo.go", "", "go"),
        ("foo.rs", "", "rust"),
        ("unknown.py", "import pytest\ndef test_foo(): pass", "python"),
        ("unknown.xyz", "describe('x', () => { it('y', () => {}); });", "typescript"),
        ("unknown.xyz", "", "python"),
    ],
)
def test_detect_stack(file_path, source_code, expected):
    assert _detect_stack(file_path, source_code) == expected


@pytest.mark.parametrize(
    "stack,framework,expected",
    [
        ("python", None, "pytest"),
        ("typescript", None, "vitest"),
        ("javascript", None, "jest"),
        ("dart", None, "flutter_test"),
        ("java", None, "junit5"),
        ("go", None, "testing"),
        ("rust", None, "cargo_test"),
        ("python", "unittest", "unittest"),
        ("unknown", None, "pytest"),
    ],
)
def test_detect_framework(stack, framework, expected):
    assert _detect_framework(stack, framework) == expected


@pytest.mark.parametrize(
    "source_path,stack,expected_suffix",
    [
        ("src/main.py", "python", "test_main.py"),
        ("src/main.ts", "typescript", "main.test.ts"),
        ("src/main.tsx", "typescript", "main.test.tsx"),
        ("src/main.js", "javascript", "main.test.js"),
        ("src/main.jsx", "javascript", "main.test.jsx"),
        ("lib/main.dart", "dart", "test/main_test.dart"),
        ("src/main/java/com/example/Main.java", "java", "Test.java"),
        ("src/main.go", "go", "main_test.go"),
        ("src/main.rs", "rust", "main_test.rs"),
    ],
)
def test_get_test_file_path(source_path, stack, expected_suffix):
    result = _get_test_file_path(source_path, stack)
    normalized = result.replace("\\", "/")
    assert normalized.endswith(expected_suffix), (result, expected_suffix)


def test_extract_python_symbols():
    source = """
class MyClass:
    def method(self, x):
        pass

def add(a, b):
    return a + b

async def fetch(url):
    pass
"""
    symbols = _extract_python_symbols(source)
    assert set(symbols["functions"]) == {"method(self, x)", "add(a, b)"}
    assert symbols["async_functions"] == ["async fetch(url)"]
    assert symbols["classes"] == ["MyClass"]


def test_extract_python_symbols_invalid_syntax():
    symbols = _extract_python_symbols("def broken(:\n    pass")
    assert symbols["functions"] == []
    assert symbols["classes"] == []
    assert symbols["async_functions"] == []


def test_clean_code(generator):
    code = "```python\ndef foo():\n    pass\n```"
    assert generator._clean_code(code, "python") == "def foo():\n    pass"
    assert generator._clean_code(code, "typescript") == "def foo():\n    pass"
    assert generator._clean_code("```\nhello\n```", "python") == "hello"
    assert generator._clean_code("no fences", "python") == "no fences"


@pytest.mark.anyio
async def test_generate_success_python(generator):
    source = "def add(a, b):\n    return a + b"
    expected = "def test_add():\n    assert add(1, 2) == 3"

    with patch.object(AutoTestGenerator, "_llm", new_callable=AsyncMock, return_value=expected):
        result = await generator.generate(source_code=source, file_path="utils.py")

    assert result["status"] == "success"
    assert result["stack"] == "python"
    assert result["framework"] == "pytest"
    assert result["file_path"] == "utils.py"
    assert result["test_file_path"] == "test_utils.py"
    assert result["test_code"] == expected
    assert result["functions_found"] == 1
    assert result["coverage_estimate"] > 0
    assert result.get("error") is None


@pytest.mark.anyio
async def test_generate_success_typescript(generator):
    source = "export const greet = (name: string): string => `Hello, ${name}`;"
    expected = "import { describe, it, expect } from 'vitest';\n\ndescribe('greet', () => {\n  it('works', () => {\n    expect(greet('x')).toBe('Hello, x');\n  });\n});"

    with patch.object(AutoTestGenerator, "_llm", new_callable=AsyncMock, return_value=expected):
        result = await generator.generate(source_code=source, file_path="greeting.ts")

    assert result["status"] == "success"
    assert result["stack"] == "typescript"
    assert result["framework"] == "vitest"
    assert result["test_file_path"] == "greeting.test.ts"
    assert result["test_code"] == expected
    assert result["functions_found"] == 0


@pytest.mark.anyio
async def test_generate_error_on_empty_llm_response(generator):
    with patch.object(AutoTestGenerator, "_llm", new_callable=AsyncMock, return_value=""):
        result = await generator.generate(source_code="def f(): pass", file_path="f.py")

    assert result["status"] == "error"
    assert result["error"] == "LLM returned empty response"
    assert result["test_code"] == ""
    assert result["test_file_path"] == "test_f.py"


@pytest.mark.anyio
async def test_generate_and_save_missing_file(generator):
    result = await generator.generate_and_save("/nonexistent/path/file.py")
    assert result["status"] == "error"
    assert "File not found" in result["error"]


@pytest.mark.anyio
async def test_generate_and_save_writes_file(tmp_path, generator):
    src = tmp_path / "module.py"
    src.write_text("def add(a, b):\n    return a + b", encoding="utf-8")
    expected_test = "def test_add():\n    assert True"

    with patch.object(
        AutoTestGenerator, "_llm", new_callable=AsyncMock, return_value=expected_test
    ):
        result = await generator.generate_and_save(str(src), run_tests=False)

    assert result["status"] == "success"
    assert result.get("saved") is True
    test_path = Path(result["test_file_path"])
    assert test_path.exists()
    assert test_path.read_text(encoding="utf-8") == expected_test


def test_run_pytest_success():
    generator = AutoTestGenerator()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="passed", stderr="")
        out = generator._run_pytest("tests/test_foo.py")
    assert out["passed"] is True
    assert out["returncode"] == 0
    mock_run.assert_called_once()


def test_run_pytest_failure():
    generator = AutoTestGenerator()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="failed", stderr="error")
        out = generator._run_pytest("tests/test_foo.py")
    assert out["passed"] is False
    assert out["returncode"] == 1


def test_run_pytest_exception():
    generator = AutoTestGenerator()
    with patch("subprocess.run", side_effect=RuntimeError("boom")):
        out = generator._run_pytest("tests/test_foo.py")
    assert out["passed"] is False
    assert out["returncode"] == -1
    assert "boom" in out["error"]


@pytest.mark.anyio
async def test_batch_generate_all_success(tmp_path, generator):
    files = []
    for i in range(3):
        p = tmp_path / f"m{i}.py"
        p.write_text(f"def f{i}(): pass\n", encoding="utf-8")
        files.append(str(p))

    results = {
        "status": "success",
        "file_path": "",
        "stack": "python",
        "framework": "pytest",
        "test_code": "def test_f(): pass\n",
        "test_file_path": "test_f.py",
        "functions_found": 1,
        "coverage_estimate": 50,
    }

    with patch.object(AutoTestGenerator, "generate", new_callable=AsyncMock, return_value=results):
        out = await generator.batch_generate(files, save=False)

    assert out["status"] == "success"
    assert out["total"] == 3
    assert out["generated"] == 3
    assert len(out["results"]) == 3


@pytest.mark.anyio
async def test_batch_generate_partial_failure(tmp_path, generator):
    files = [str(tmp_path / "ok.py"), str(tmp_path / "bad.py")]
    (tmp_path / "ok.py").write_text("def ok(): pass\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def bad(): pass\n", encoding="utf-8")

    ok_result = {
        "status": "success",
        "file_path": str(tmp_path / "ok.py"),
        "stack": "python",
        "framework": "pytest",
        "test_code": "def test_ok(): pass\n",
        "test_file_path": "test_ok.py",
        "functions_found": 1,
        "coverage_estimate": 50,
    }
    bad_result = {
        "status": "error",
        "file_path": str(tmp_path / "bad.py"),
        "stack": "python",
        "framework": "pytest",
        "test_code": "",
        "test_file_path": "test_bad.py",
        "functions_found": 0,
        "coverage_estimate": 0,
        "error": "LLM returned empty response",
    }

    async def fake_generate(*, source_code, file_path, **kwargs):
        if "bad" in file_path:
            return bad_result
        return ok_result

    with patch.object(AutoTestGenerator, "generate", side_effect=fake_generate):
        out = await generator.batch_generate(files, save=False)

    assert out["status"] == "success"
    assert out["total"] == 2
    assert out["generated"] == 1


@pytest.mark.anyio
async def test_generate_llm_exception_returns_error(generator):
    with (
        patch.object(
            AutoTestGenerator,
            "_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("oops"),
        ),
        pytest.raises(RuntimeError, match="oops"),
    ):
        await generator.generate(source_code="def f(): pass", file_path="f.py")


def test_request_response_models():
    req = TestGenRequest(source_code="def foo(): pass", file_path="foo.py")
    assert req.coverage_target == 80
    assert req.include_mocks is True
    assert req.include_edge_cases is True

    resp = TestGenResponse(
        status="success",
        file_path="foo.py",
        stack="python",
        framework="pytest",
        test_code="def test_foo(): pass",
        test_file_path="test_foo.py",
        functions_found=1,
        coverage_estimate=80,
    )
    assert resp.status == "success"
    assert resp.error is None


@pytest.mark.anyio
async def test_supported_stacks_endpoint():
    endpoint = None
    for r in router.routes:
        if getattr(r, "name", None) == "supported_stacks":
            endpoint = r.endpoint
            break
    assert endpoint is not None
    result = await endpoint()
    assert "stacks" in result
    assert "python" in result["stacks"]
    assert result["frameworks"]["python"] == "pytest"


@pytest.mark.anyio
async def test_llm_method(monkeypatch):
    generator = AutoTestGenerator()
    captured = {}

    async def fake_route(self, prompt, *, task_type, max_cost):
        captured["task_type"] = task_type
        captured["max_cost"] = max_cost
        return {"text": "def test_foo():\n    pass"}

    monkeypatch.setattr(
        "brain.model_router.ModelRouter",
        type("R", (), {"async_route_and_generate": fake_route}),
    )
    out = await generator._llm("prompt")
    assert out == "def test_foo():\n    pass"
    assert captured["task_type"] == "coding"
    assert captured["max_cost"] == 0.05


@pytest.fixture
def client(generator):
    try:
        from api import app as _app

        app = _app
    except Exception:
        from fastapi import FastAPI

        from tools.code.auto_test_generator import router as test_router

        app = FastAPI()
        app.include_router(test_router)
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.mark.anyio
async def test_llm_method_exception():
    generator = AutoTestGenerator()
    with patch("brain.model_router.ModelRouter", side_effect=RuntimeError("fail")):
        out = await generator._llm("prompt")
    assert out == ""


@pytest.mark.anyio
async def test_llm_method_non_dict_result(monkeypatch):
    generator = AutoTestGenerator()

    class R:
        async def async_route_and_generate(self, *args, **kwargs):
            return "plain text"

    monkeypatch.setattr("brain.model_router.ModelRouter", R)
    out = await generator._llm("prompt")
    assert out == "plain text"


@pytest.mark.anyio
async def test_generate_and_save_returns_early_on_generate_error(tmp_path, generator):
    src = tmp_path / "dummy.py"
    src.write_text("def f(): pass\n", encoding="utf-8")
    with patch.object(
        AutoTestGenerator,
        "generate",
        new_callable=AsyncMock,
        return_value={"status": "error", "error": "bad", "file_path": str(src)},
    ):
        result = await generator.generate_and_save(str(src))
    assert result["status"] == "error"
    assert result["error"] == "bad"
    assert result.get("saved") is None


@pytest.mark.anyio
async def test_generate_and_save_runs_pytest(tmp_path, generator):
    src = tmp_path / "module.py"
    src.write_text("def add(a, b):\n    return a + b", encoding="utf-8")
    expected_test = "def test_add():\n    assert True"

    with (
        patch.object(
            AutoTestGenerator,
            "_llm",
            new_callable=AsyncMock,
            return_value=expected_test,
        ),
        patch.object(
            generator,
            "_run_pytest",
            new_callable=MagicMock,
            return_value={"passed": True, "returncode": 0},
        ) as run_mock,
    ):
        result = await generator.generate_and_save(str(src), run_tests=True)

    assert result["status"] == "success"
    assert result["saved"] is True
    run_mock.assert_called_once()


@pytest.mark.anyio
async def test_batch_generate_save_true(tmp_path, generator):
    p = tmp_path / "mod.py"
    p.write_text("def foo(): pass\n", encoding="utf-8")
    expected_test = "def test_foo():\n    pass"

    with patch.object(
        AutoTestGenerator,
        "generate_and_save",
        new_callable=AsyncMock,
        return_value={
            "status": "success",
            "test_file_path": str(tmp_path / "test_mod.py"),
            "test_code": expected_test,
            "functions_found": 1,
            "coverage_estimate": 50,
        },
    ):
        out = await generator.batch_generate([str(p)], save=True)

    assert out["total"] == 1
    assert out["generated"] == 1


@pytest.mark.anyio
async def test_generate_endpoint_success(client):
    from fastapi.testclient import TestClient

    from tools.code.auto_test_generator import _generator

    app = None
    try:
        from api import app as _app

        app = _app
    except Exception:
        app = None

    if app is None:
        from fastapi import FastAPI

        from tools.code.auto_test_generator import router as test_router

        app = FastAPI()
        app.include_router(test_router)

    with (
        TestClient(app) as c,
        patch.object(
            _generator,
            "generate",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "file_path": "f.py",
                "stack": "python",
                "framework": "pytest",
                "test_code": "def test_f(): pass\n",
                "test_file_path": "test_f.py",
                "functions_found": 1,
                "coverage_estimate": 80,
            },
        ),
    ):
        resp = c.post("/test-gen/generate", json={"source_code": "def f(): pass"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@pytest.mark.anyio
async def test_generate_endpoint_error(client):
    from fastapi.testclient import TestClient

    from tools.code.auto_test_generator import _generator

    app = None
    try:
        from api import app as _app

        app = _app
    except Exception:
        app = None

    if app is None:
        from fastapi import FastAPI

        from tools.code.auto_test_generator import router as test_router

        app = FastAPI()
        app.include_router(test_router)

    with (
        TestClient(app) as c,
        patch.object(
            _generator,
            "generate",
            new_callable=AsyncMock,
            return_value={
                "status": "error",
                "error": "LLM returned empty response",
                "file_path": "f.py",
                "stack": "python",
                "framework": "pytest",
                "test_code": "",
                "test_file_path": "test_f.py",
                "functions_found": 0,
                "coverage_estimate": 0,
            },
        ),
    ):
        resp = c.post("/test-gen/generate", json={"source_code": "def f(): pass"})
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_generate_file_endpoint(client, generator):
    from fastapi.testclient import TestClient

    app = None
    try:
        from api import app as _app

        app = _app
    except Exception:
        app = None

    if app is None:
        from fastapi import FastAPI

        from tools.code.auto_test_generator import router as test_router

        app = FastAPI()
        app.include_router(test_router)

    with (
        TestClient(app) as c,
        patch.object(
            generator,
            "generate",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "file_path": "upload.py",
                "stack": "python",
                "framework": "pytest",
                "test_code": "def test_u(): pass\n",
                "test_file_path": "test_upload.py",
                "functions_found": 1,
                "coverage_estimate": 80,
            },
        ),
    ):
        resp = c.post("/test-gen/generate-file", files={"file": ("upload.py", b"def f(): pass")})
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_batch_endpoint_max_files(generator):
    paths = [f"file{i}.py" for i in range(21)]
    with pytest.raises(ValueError):
        await generator.batch_generate(paths, save=False)
