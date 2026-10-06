# Memory Governance — Policy-Driven TTL (issue #4053)

> **Priority:** P3 — design document (implementation will follow in a separate PR)
> **Date:** 2026-10-06
> **Roadmap v2 section:** Phase 3 → §3.3 Memory Governance
> **Source:** Memanto-inspired concepts, adapted to SupremeAI's architecture

## Mission

Adopt Memanto-inspired memory governance with **policy-driven TTL** (not hardcoded). Design the policy engine that governs memory lifecycle: when to expire, when to merge, when to flag conflicts.

## Design (Policy-Driven, NOT Hardcoded)

### Anti-Pattern (Rejected)
```python
# ❌ WRONG — hardcoded TTL by type
if memory.type == "procedural":
    ttl = PERMANENT
elif memory.type == "episodic":
    ttl = 30 * DAYS
elif memory.type == "cache":
    ttl = 1 * HOUR
```

### Correct Pattern (Policy-Driven)
```python
# ✅ CORRECT — TTL computed from multiple inputs per entry
ttl = memory_policy_engine.compute_ttl(
    type=entry.type,                    # procedural / episodic / cache / decision
    importance=entry.importance_score,  # 0.0 - 1.0
    confidence=entry.confidence_level,  # 0.0 - 1.0
    verification=entry.verification_status,  # verified / unverified / failed
    usage_frequency=entry.retrieval_count,   # how often retrieved
    freshness=entry.age_days,                # how recent
    risk_level=entry.risk_level,             # what happens if stale
)
# Result: dynamic TTL per entry, not per type
```

## Policy Engine Inputs

| Input | Source | Type | Weight (configurable) |
|---|---|---|---|
| `type` | Memory entry type field | enum (procedural/episodic/cache/decision) | base |
| `importance` | Importance score | float 0.0-1.0 | high |
| `confidence` | Confidence level | float 0.0-1.0 | high |
| `verification` | Verification status (#4052) | enum (verified/unverified/failed) | critical |
| `usage_frequency` | Retrieval count | int | medium |
| `freshness` | Age in days | int | medium |
| `risk_level` | Risk if stale | enum (low/medium/high/critical) | high |

## TTL Computation Rules (examples)

| Scenario | TTL |
|---|---|
| High importance + verified + frequently used | PERMANENT |
| Low confidence + unverified + stale | SHORT (7 days) |
| Decision metadata + verified + recent | LONG (180 days) |
| Cache entry + low usage + old | EXPIRE (1 day) |
| High risk + stale | IMMEDIATE REVIEW (flag for admin) |

## Conflict Detection

When two entries with the same semantic key have different values:
1. **Auto-merge** if values are compatible (e.g., different timestamps of same fact)
2. **Flag for admin review** if values conflict (e.g., contradictory decisions)
3. **Provenance chain** preserved — both entries linked via `supersedes` field (#4052)

## Provenance

Every memory entry has a `source_decision_id` linking back to `DecisionMetadata` (#4052). This enables:
- "Why was this memory created?" → trace to the decision
- "Is this memory still valid?" → check if the decision was superseded
- "What happens if I delete this?" → see what depends on it

## Expiry Sweep (cron job)

```python
# scripts/cron/memory_expiry_sweep.py (to be implemented)
# Runs daily:
# 1. Query all entries where expires_at < now()
# 2. For each expired entry:
#    a. If verified + high-importance → ARCHIVE (move to long_term_memory, don't delete)
#    b. If unverified + low-importance → DELETE
#    c. If conflict-flagged → SKIP (admin must resolve first)
# 3. Log sweep results (structured, #3415 PII redaction)
```

## Admin-Configurable Policy Weights

Policy weights are stored in a YAML config (NOT hardcoded in Python):
```yaml
# config/memory_policy.yml (to be implemented)
ttl_weights:
  importance: 0.3
  confidence: 0.25
  verification: 0.25
  usage_frequency: 0.1
  freshness: 0.1

ttl_thresholds:
  permanent: 0.8   # score >= 0.8 → permanent
  long: 0.6         # 0.6-0.8 → 180 days
  medium: 0.4       # 0.4-0.6 → 30 days
  short: 0.2        # 0.2-0.4 → 7 days
  expire: 0.0       # < 0.2 → 1 day
```

## Implementation Plan (separate PR)

1. `backend/memory/policy_engine_memory.py` — TTL computation engine
2. `backend/memory/conflict_detector.py` — conflict detection
3. `backend/memory/provenance.py` — provenance chain
4. `config/memory_policy.yml` — admin-configurable weights
5. `scripts/cron/memory_expiry_sweep.py` — daily sweep job
6. `prisma/schema.prisma` — `MemoryPolicy` + `MemoryConflict` models
7. Tests: unit tests for TTL computation + conflict detection

## Decision: DESIGN APPROVED — implementation deferred to separate PR

**Rationale:** This design document establishes the policy-driven TTL pattern. Implementation will follow in a separate PR once the Decision Metadata model (#4052, already merged) is fully wired into the memory pipeline.

## Bengali Note

TTL কখনো hardcoded নয় — policy-driven। high-importance + verified = permanent; low-confidence + unverified + stale = short TTL। এটা Memanto থেকে ধার করা concept কিন্তু SupremeAI-তে policy engine আকারে বাস্তবায়িত হবে। প্রতিটি entry-র জন্য dynamic TTL compute হবে।
