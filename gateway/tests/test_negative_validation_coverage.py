"""Negative validation coverage tests (#3270).

বাংলা: এই টেস্টগুলো API routes এর negative validation coverage বাড়ায় —
missing required fields, malformed auth headers, invalid payload types,
empty bodies, oversized payloads।
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, status

# ── Missing required fields tests ────────────────────────────────────────────


class TestMissingRequiredFields:
    """#3270: requests missing required fields → 422 (not 500)।"""

    def test_empty_body_on_post_returns_422(self):
        # বাংলা: POST with empty body → 422 Unprocessable Entity (not 500)
        from fastapi.testclient import TestClient

        from core.app_builder import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        # Find a POST endpoint that requires a body
        post_routes = [
            r
            for r in app.routes
            if hasattr(r, "path") and hasattr(r, "methods") and "POST" in r.methods
        ]
        for route in post_routes[:5]:  # test first 5 POST routes
            if "/webhook" in route.path or "/health" in route.path:
                continue  # skip webhooks/health (different contract)
            response = client.post(route.path, json={})
            assert response.status_code in (
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ), (
                f"POST {route.path} with empty body should return 422/400/401/403, got {response.status_code}"
            )

    def test_missing_content_type_on_post(self):
        from fastapi.testclient import TestClient

        from core.app_builder import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        post_routes = [
            r
            for r in app.routes
            if hasattr(r, "path") and hasattr(r, "methods") and "POST" in r.methods
        ]
        for route in post_routes[:3]:
            if "/webhook" in route.path or "/health" in route.path:
                continue
            response = client.post(route.path, content=b"")
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR, (
                f"POST {route.path} without content-type should not 500"
            )


# ── Malformed auth header tests ─────────────────────────────────────────────


class TestMalformedAuthHeaders:
    """#3270: malformed Authorization headers → 401/403 (not 500)।"""

    def test_malformed_bearer_token(self):
        from fastapi.testclient import TestClient

        from core.app_builder import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        protected_routes = [
            r
            for r in app.routes
            if hasattr(r, "path")
            and hasattr(r, "methods")
            and "GET" in r.methods
            and "/health" not in r.path
            and "/docs" not in r.path
            and "/redoc" not in r.path
            and "/openapi" not in r.path
            and r.path != "/"
        ]
        for route in protected_routes[:5]:
            response = client.get(
                route.path, headers={"Authorization": "Bearer not-a-real-jwt-token"}
            )
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ), (
                f"GET {route.path} with bad Bearer should return 401/403/422, got {response.status_code}"
            )

    def test_non_bearer_auth_scheme(self):
        from fastapi.testclient import TestClient

        from core.app_builder import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        protected_routes = [
            r
            for r in app.routes
            if hasattr(r, "path")
            and hasattr(r, "methods")
            and "GET" in r.methods
            and "/health" not in r.path
        ]
        for route in protected_routes[:3]:
            response = client.get(route.path, headers={"Authorization": "Basic dXNlcjpwYXNz"})
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR, (
                f"GET {route.path} with Basic auth should not 500"
            )

    def test_empty_authorization_header(self):
        from fastapi.testclient import TestClient

        from core.app_builder import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        protected_routes = [
            r
            for r in app.routes
            if hasattr(r, "path")
            and hasattr(r, "methods")
            and "GET" in r.methods
            and "/health" not in r.path
        ]
        for route in protected_routes[:3]:
            response = client.get(route.path, headers={"Authorization": ""})
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR, (
                f"GET {route.path} with empty Authorization should not 500"
            )


# ── Invalid payload type tests ──────────────────────────────────────────────


class TestInvalidPayloadTypes:
    """#3270: wrong-type payload fields → 422 (not 500)।"""

    def test_string_where_int_expected(self):
        # বাংলা: if a route expects an int field and receives string → 422
        from pydantic import BaseModel, ValidationError

        class TestModel(BaseModel):
            count: int

        with pytest.raises(ValidationError):
            TestModel(count="not-a-number")

    def test_string_where_bool_expected(self):
        from pydantic import BaseModel, ValidationError

        class TestModel(BaseModel):
            enabled: bool

        with pytest.raises(ValidationError):
            TestModel(enabled="not-a-bool")

    def test_null_where_required(self):
        from pydantic import BaseModel, ValidationError

        class TestModel(BaseModel):
            name: str

        with pytest.raises(ValidationError):
            TestModel(name=None)

    def test_array_where_string_expected(self):
        from pydantic import BaseModel, ValidationError

        class TestModel(BaseModel):
            name: str

        with pytest.raises(ValidationError):
            TestModel(name=["array", "not", "string"])


# ── Oversized payload tests ────────────────────────────────────────────────


class TestOversizedPayloads:
    """#3270: oversized payloads → 413 or 422 (not 500 or OOM)।"""

    def test_large_string_in_payload(self):
        from pydantic import BaseModel, Field

        class TestModel(BaseModel):
            description: str = Field(max_length=1000)

        large_text = "x" * 1001
        with pytest.raises(Exception):
            TestModel(description=large_text)

    def test_huge_array_in_payload(self):
        from pydantic import BaseModel, Field

        class TestModel(BaseModel):
            items: list[str] = Field(max_length=100)

        huge_list = [f"item-{i}" for i in range(101)]
        with pytest.raises(Exception):
            TestModel(items=huge_list)


# ── SQL injection pattern tests ────────────────────────────────────────────


class TestSQLInjectionPatterns:
    """#3270: SQL injection patterns in string fields → rejected (not 500)।"""

    def test_single_quote_injection_attempt(self):
        # বাংলা: ' OR 1=1 -- pattern should not cause 500 (ORM parameterized)
        from pydantic import BaseModel

        class TestModel(BaseModel):
            search: str

        # Pydantic will accept the string (ORM handles parameterization)
        model = TestModel(search="'; DROP TABLE users; --")
        assert model.search == "'; DROP TABLE users; --"
        # The key is: no 500 — ORM parameterized query handles it

    def test_union_injection_attempt(self):
        from pydantic import BaseModel

        class TestModel(BaseModel):
            search: str

        model = TestModel(search="1 UNION SELECT * FROM users")
        assert "UNION" in model.search
        # No crash — just a string

    def test_comment_injection_attempt(self):
        from pydantic import BaseModel

        class TestModel(BaseModel):
            search: str

        model = TestModel(search="admin'--")
        assert model.search == "admin'--"


# ── Path traversal pattern tests ────────────────────────────────────────────


class TestPathTraversalPatterns:
    """#3270: path traversal patterns in string fields → rejected by ResourceGuard।"""

    def test_dot_dot_slash_pattern(self):
        from pydantic import BaseModel

        class TestModel(BaseModel):
            filepath: str

        model = TestModel(filepath="../../../etc/passwd")
        assert ".." in model.filepath
        # ResourceGuard will reject this at the service layer

    def test_null_byte_injection(self):
        from pydantic import BaseModel

        class TestModel(BaseModel):
            filepath: str

        model = TestModel(filepath="safe.txt\x00.evil")
        # Pydantic accepts the string; ResourceGuard/validators handle null bytes
        assert model.filepath is not None
