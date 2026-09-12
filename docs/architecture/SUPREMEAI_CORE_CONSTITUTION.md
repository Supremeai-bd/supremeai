# SupremeAI Core Constitution

This document is the authoritative cross-cutting constitution for SupremeAI. It applies to every Circle, module, agent, integration, execution path, and deployment.

## Universal principles

1. **Centralize important control.** Distributed implementations are allowed; fragmented governance is not.
2. **Build complete Circles.** Every capability must connect to the wider system and increase reusable platform power.
3. **Reuse before creation.** Discover existing and authorized capabilities before creating new infrastructure.
4. **Keep provider sovereignty.** External services are replaceable capabilities; SupremeAI retains orchestration, policy, permissions, and visibility.
5. **Preserve tenant ownership.** Every operation must resolve and enforce tenant and actor scope.
6. **Think before acting.** Risk, authorization, and human approval precede consequential actions.
7. **Learning requires governance.** Evidence and review are required before consequential autonomous evolution.
8. **Verify before trust.** Important results, changes, and autonomous actions require observable verification.
9. **Optimize cost without limiting user choice.** Prefer sustainable cloud-native paths while honoring explicit performance choices.
10. **Make important behavior observable.** Failures, degraded modes, decisions, and side effects must leave useful evidence.

## Required execution order

```text
Discover → Resolve tenant/actor → Authorize/policy → Execute → Verify → Audit → Learn
```

Implementations that conflict with these principles must stop and resolve the architectural conflict rather than weakening the rule for local convenience. This file is intentionally concise; the repository architecture documentation provides the detailed implementation guidance and examples.

## Cloud-native parity

Production behavior must be reproducible through the repository's CI/CD and managed cloud services. Manual local-machine workarounds, local tunnels, and untracked credentials are not acceptable substitutes for production mechanisms.

## Change requirements

Changes affecting routing, integrations, persistence, agents, or autonomous actions must preserve tenant isolation, fail-closed security boundaries, rollback evidence, and machine-verifiable tests.

> Source of truth: the SupremeAI architecture corpus and repository `AGENTS.md`. Update this constitution and the architecture documentation together when a universal rule changes.
