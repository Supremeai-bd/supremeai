# Modular Monolith Target Architecture

## Purpose

SupremeAI will evolve toward a modular monolith for the core backend while preserving independently deployed services where their runtime, security, or failure profile requires separation. The target is a set of explicit domain boundaries, stable public capabilities, owned persistence, and evidence-gated migration—not a folder-only reorganization or a mandatory single process.

## Domain boundaries

| Domain | Responsibility | Initial owner | Lifecycle |
|---|---|---|---|
| Identity/Auth | Users, sessions, credentials, authorization context | Platform | operational |
| AI/LLM | Model policy, prompts, generation orchestration | AI | operational |
| Execution/Worker | Jobs, tools, task execution, retries | Runtime | operational |
| Memory/Knowledge | Ingestion, retrieval, knowledge lifecycle | Knowledge | operational |
| Browser/Research | Browser-heavy research and web acquisition | Research | operational |
| Data/Storage | Shared storage primitives and migrations | Data | operational |
| Governance/Security | Policy, audit, risk gates, tenant isolation | Security | operational |
| Billing | Plans, quotas, usage and billing controls | Commerce | owner-review |
| Observability | Logs, metrics, traces, operational evidence | Platform | operational |

Ownership is architectural metadata until package-level enforcement is added. Partially wired, dormant, and environment-dependent capabilities remain in an owner-review queue.

## Boundary rules

1. Consumers may call another domain only through a documented public capability, facade, adapter, or versioned event.
2. Consumers must not import another domain's private implementation, repository, persistence model, or internal test helper.
3. A domain owns writes to its persistence. Cross-domain reads use a public query capability or projection.
4. Every request crossing a domain boundary carries authenticated actor and tenant context.
5. Errors are typed at the public boundary; implementation exceptions do not leak across domains.
6. Existing routes and deployed services remain compatible through adapters during migration.

## Deployment model

The core backend may remain a modular monolith. `supremeai-scraper` remains an independent deployed service because browser/network workload and failure isolation differ from the core runtime. Extraction is optional and follows proven contracts, operational evidence, and rollback capability.

## Migration policy

Each migration freezes a baseline, selects a bounded pilot, introduces a facade and anti-corruption adapter, enforces the boundary in CI, and proves rollback. No mass refactoring begins until dependency graph, ownership, contract coverage, tenant isolation, compatibility, latency, error, and recovery evidence meet the phase gate.

## Pilot policy

Knowledge/ingestion is the default candidate because it has existing operational and caller evidence. The generated dependency graph and blast-radius report must confirm that it is lower risk than Execution/Worker before implementation is promoted. The pilot must preserve current callers and routes, own its writes, and support disabling the facade without data loss.

## Evidence and approval

Every domain change records owner, affected callers, dependency edges, contract version, tests, rollout state, baseline comparison, and rollback evidence. Medium-risk changes require staged rollout and human visibility; high-risk changes affecting identity, security, billing, tenant isolation, destructive data operations, or production-wide infrastructure require explicit governance approval.

## Success criteria

Phase 1 succeeds when undocumented dependencies, private cross-domain imports, cycles, and unowned writes decrease or remain controlled; preserved callers remain compatible; tenant-isolation failures remain zero; error and latency remain within frozen thresholds; and rollback is demonstrated with no data loss.

See `module_contract.schema.yaml` for the contract shape and `docs/generated/domain_dependency_graph.json` for generated evidence.

## Non-goals

- Rewriting all existing modules.
- Creating a second module registry.
- Converting every deployed service into one process.
- Immediate microservice extraction.
- Broad database rewrites without ownership and rollback evidence.
