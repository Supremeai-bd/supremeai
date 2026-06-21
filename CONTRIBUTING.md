# Contributing to SupremeAI 2.0

We welcome contributions! Please follow these guidelines to keep the monorepo clean and structured.

## Development Workflow

1. Fork the repository and create your branch from `main`.
2. Follow the monorepo design principles: keep shared types under `packages/shared-types` and backend code under `backend/`.
3. Adhere to coding standards defined in `docs/02-governance/.antigravityrules`.
4. Ensure all unit tests pass before requesting review.

## Pull Request Guidelines

- Include details about what changes you are introducing.
- Verify tests pass locally using `poetry run pytest` inside the `backend/` directory.
- Update relevant documents inside the `docs/` folder.
