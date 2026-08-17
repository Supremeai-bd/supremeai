# Coding Standards

## Overview

This document defines the coding standards and conventions for SupremeAI 2.0. Following these standards ensures consistency, maintainability, and quality across the codebase.

## Python Standards

### Style Guide

- Follow **PEP 8** style guide
- Use **4 spaces** for indentation (no tabs)
- Maximum line length: **88 characters** (configured in `pyproject.toml`)
- Use **type hints** for all function signatures
- Use **docstrings** (Google style) for all public functions and classes

### Example

```python
"""Module docstring describing the purpose of this module."""

from typing import Optional, List
from loguru import logger


class SupremeCache:
    """
    সিমান্টিক ক্যাশ ইঞ্জিন
    বাংলা মন্তব্য: এটি ডুপ্লিকেট রিকোয়েস্ট ডিটেক্ট করে এবং একই রেসপন্স শেয়ার করে
    """

    def __init__(self, ttl: int = 300) -> None:
        """Initialize the cache with a time-to-live.

        Args:
            ttl: Time-to-live in seconds for cached entries.
        """
        self.ttl = ttl
        self._store: dict[str, any] = {}

    async def get(self, key: str) -> Optional[any]:
        """Retrieve a value from the cache.

        Args:
            key: The cache key to look up.

        Returns:
            The cached value or None if not found.
        """
        return self._store.get(key)
```

### Error Handling

```python
try:
    result = await api_call()
except TimeoutError:
    logger.warning(f"API timeout, using fallback model")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### Logging

```python
from loguru import logger

logger.info(f"✅ Feature enabled for user {user_id}")
logger.warning(f"⚠️ Deprecated API endpoint called")
logger.error(f"❌ Critical failure in payment processing")
```

### Comments

- Use **Bengali comments** for complex logic (as per project convention)
- Include **English translations** for non-Bengali speakers
- Keep comments concise and up-to-date

## JavaScript/TypeScript Standards

- Use **ESLint** with Prettier for formatting
- Use **TypeScript** for all new code (strict mode enabled)
- Use **camelCase** for variables and functions
- Use **PascalCase** for components and classes
- Use **UPPER_SNAKE_CASE** for constants

## Git Conventions

### Commit Messages

Use conventional commits format:

```
feat: Add new agent workflow execution endpoint
fix: Resolve JWT secret persistence issue
docs: Update API documentation for webhooks
refactor: Consolidate circuit breaker implementations
test: Add integration tests for auth flow
```

### Branching

- `main` — production-ready code
- `develop` — integration branch
- `feature/*` — new features
- `fix/*` — bug fixes
- `docs/*` — documentation changes

## Security Standards

- Never hardcode secrets — use environment variables
- All sensitive endpoints require JIT OTP verification
- Validate all inputs with Pydantic schemas
- Use parameterized queries for database operations
- Enable AST scanning for code execution endpoints
