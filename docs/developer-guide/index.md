# SupremeAI 2.0 Developer Guide

Welcome to the SupremeAI 2.0 Developer Guide. This comprehensive guide covers everything you need to know to develop, test, deploy, and contribute to SupremeAI 2.0.

## Table of Contents

| Guide | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Set up your development environment |
| [Architecture](architecture.md) | Understand the system architecture |
| [Coding Standards](coding-standards.md) | Follow project coding conventions |
| [Testing](testing.md) | Run and write tests |
| [Deployment](deployment.md) | Deploy to production |
| [Contributing](contributing.md) | Contribute to the project |
| [Troubleshooting](troubleshooting.md) | Resolve common issues |

## Quick Links

- **API Documentation**: [docs/api/v1/index.md](../api/v1/index.md)
- **Master Blueprint**: [SUPREMEAI_MASTER_BLUEPRINT.md](../SUPREMEAI_MASTER_BLUEPRINT.md)
- **Architecture Overview**: [architecture-overview.md](../architecture-overview.md)
- **Project Roadmap**: [ROADMAP_IMPLEMENTATION_SUMMARY.md](../../ROADMAP_IMPLEMENTATION_SUMMARY.md)

## Development Quick Reference

```bash
# Start backend
pnpm backend:dev

# Start frontend
cd apps/studio-client && pnpm dev

# Run tests
pnpm backend:test

# Run linting
pnpm turbo run lint

# Deploy
python scripts/deploy.py --env production
```

## Core Principles

1. **Zero Cost**: Use free-tier services exclusively
2. **High Scalability**: Async, non-blocking architecture
3. **Zero Breakage**: Preserve production state with delta patches
4. **Human-in-the-Loop**: JIT OTP for sensitive operations
5. **Malware Immunity**: JIT defense + IP churn detection
6. **Self-Healing**: Autonomous error remediation
7. **Failure-Aware**: Learn from past failures

## Need Help?

- **Discord**: [SupremeAI Community](https://discord.gg/supremeai)
- **GitHub Discussions**: [Community discussions](https://github.com/SaifulHaqueNiloy/supremeai/discussions)
- **Email**: dev-support@supremeai.dev
