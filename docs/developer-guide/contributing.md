# Contributing to SupremeAI 2.0

## Overview

Thank you for your interest in contributing to SupremeAI 2.0! This document outlines the process for contributing code, documentation, and other improvements.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a virtual environment and install dependencies (see [Getting Started](getting-started.md))
4. Create a new branch for your changes

## Development Workflow

### 1. Create a Branch

```bash
# Create a feature branch
git checkout -b feature/my-new-feature

# Or a fix branch
git checkout -b fix/my-bug-fix
```

### 2. Make Changes

- Follow the [Coding Standards](coding-standards.md)
- Write tests for new functionality
- Update documentation as needed
- Keep changes focused and minimal

### 3. Run Tests

```bash
# Run backend tests
pnpm backend:test

# Run frontend tests
pnpm turbo run test

# Run linting
pnpm turbo run lint
```

### 4. Commit Changes

Use conventional commit format:

```bash
git commit -m "feat: Add new agent workflow execution endpoint"
git commit -m "fix: Resolve JWT secret persistence issue"
git commit -m "docs: Update API documentation for webhooks"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/my-new-feature
```

Then create a Pull Request on GitHub.

## Pull Request Process

1. Ensure all tests pass
2. Ensure code coverage doesn't decrease
3. Get at least one review from the team
4. Address any feedback
5. Merge when approved

## Code Review Guidelines

### What to Look For

- **Correctness**: Does the code do what it's supposed to?
- **Security**: Are there any security vulnerabilities?
- **Performance**: Could the code be optimized?
- **Readability**: Is the code clear and well-documented?
- **Test Coverage**: Are there adequate tests?

### Review Checklist

- [ ] Code follows coding standards
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No hardcoded secrets
- [ ] Error handling is appropriate
- [ ] Logging is consistent
- [ ] Type hints are used

## Reporting Issues

### Bug Reports

When reporting a bug, please include:

1. A clear and descriptive title
2. Steps to reproduce the issue
3. Expected behavior
4. Actual behavior
5. Environment details (OS, Python version, etc.)
6. Relevant logs or error messages

### Feature Requests

When requesting a feature, please include:

1. A clear and descriptive title
2. The problem the feature would solve
3. Your proposed solution
4. Any alternatives you've considered

## Community

- **Discord**: Join our Discord server for real-time discussion
- **GitHub Discussions**: Use for longer-form discussions
- **Email**: Contact the team at team@supremeai.dev

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Give constructive feedback
- Focus on the code, not the person

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
