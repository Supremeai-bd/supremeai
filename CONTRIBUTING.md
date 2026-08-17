# Contributing to SupremeAI 2.0

## Getting Started
Please read our documentation before starting.
When creating new branches, make sure to use `git checkout -b feature/name` or `git commit -m "feat: your change"`.
Remember that Safety Guard rules apply to all code.

## Testing
- Run `pnpm backend:test` to test the backend.
- Test examples are available in `backend/tests`.
- When writing tests, make sure to prefix functions with `test_` and use `@pytest.fixture` where appropriate.

## Coding Standards
We use Python 3.11+, Poetry, Ruff, MyPy, and pytest.
# বাংলা মন্তব্য: সর্বদা কোডে যথাযথ মন্তব্য যোগ করুন।

Multi-Model Validator is used to validate LLM responses.
Autocache is used for performance optimization.
Codegraph mapping is used for structural dependency checks and code navigation.
AI Agent orchestrator handles dynamic task execution.
