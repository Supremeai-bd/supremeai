# Testing Guide

## Overview

SupremeAI 2.0 uses a comprehensive testing strategy including unit tests, integration tests, performance tests, security tests, and chaos testing. This guide explains how to run and write tests.

## Test Structure

```
backend/tests/
├── unit/                    # Unit tests for individual modules
├── integration/             # Integration tests for API endpoints
├── security/                # Security-focused tests
├── performance/             # Performance and load tests
└── conftest.py              # Shared test fixtures
```

## Running Tests

### Backend Tests (pytest)

```bash
# Run all backend tests
pnpm backend:test

# Run with coverage
poetry run pytest backend/tests/ -v --cov=core

# Run specific test file
poetry run pytest backend/tests/unit/test_circuit_breaker.py -v

# Run tests matching a pattern
poetry run pytest backend/tests/ -k "auth" -v

# Run with parallel execution
poetry run pytest backend/tests/ -n auto
```

### Frontend Tests

```bash
# Run all frontend tests
pnpm turbo run test

# Run tests for a specific app
cd apps/studio-client
pnpm test

# Run with coverage
pnpm test --coverage
```

### Test Categories

| Category | Command | Coverage Target |
|----------|---------|-----------------|
| Unit Tests | `pytest backend/tests/unit/` | 90% |
| Integration Tests | `pytest backend/tests/integration/` | 80% |
| Security Tests | `pytest backend/tests/security/` | 85% |
| Performance Tests | `pytest backend/tests/performance/` | N/A |
| End-to-End | `playwright test` | 70% |

## Writing Tests

### Unit Test Example

```python
import pytest
from core.circuit_breaker import CircuitBreaker


@pytest.fixture
def circuit_breaker():
    return CircuitBreaker("test_service", failure_threshold=3)


def test_circuit_opens_after_failures(circuit_breaker):
    """Test that circuit opens after threshold failures."""
    for _ in range(3):
        circuit_breaker.record_failure()

    assert not circuit_breaker.can_execute()
```

### Integration Test Example

```python
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_login(client):
    """Test successful authentication."""
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

## Test Coverage

Current coverage targets:

| Module | Current | Target |
|--------|---------|--------|
| Core Resilience | 45% | 90% |
| API Routes | 55% | 85% |
| Security | 60% | 90% |
| Tools/Agents | 35% | 75% |

## CI/CD Integration

Tests run automatically on every push:

1. **Circuit Breaker**: Check previous run status
2. **Detect Changes**: Identify modified files
3. **Backend Tests**: Run pytest suite
4. **Frontend Tests**: Run pnpm test
5. **Security Scan**: Check critical file changes
6. **Coverage Report**: Upload to CI step summary
