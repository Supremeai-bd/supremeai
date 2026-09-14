# Rate Limiting Contract — Redis Authoritative (P1)

> Owner policy: **Redis = authoritative rate limiter; in-memory = documented
> emergency fallback only.**

## The three limiter layers

| Layer | Location | Authority | Fallback |
| --- | --- | --- | --- |
| `RateLimitMiddleware` (tiered: anonymous/authenticated/premium/admin + endpoint overrides) | `core/rate_limit.py` | Redis sliding window (two-phase: prune+count, then add-on-allow) via centralized `redis_manager` | `fallback_cache` in-memory dict, logged at WARNING |
| `RequestValidationMiddleware` (security pre-filter: login/register/scraper/kaggle strict paths) | `core/middleware/security.py` | Redis sliding window keyed `security_rate_limit:<ip-or-ip:path>` | per-instance `_request_log` dict, logged as **EMERGENCY** |
| `GlobalRateLimiterMiddleware` + `AsyncRateLimiter` (tiered per API-key prefix) | `middleware/rate_limiter.py`, `api/middleware.py` | Redis sliding window via `redis_manager` | `InMemoryFallbackLimiter`, logged at WARNING |

## Why Redis is the authority

The in-memory fallbacks are **per-process**. With `2+ core instances`:

```
Instance A → 5 requests   Instance B → 5 requests   ⇒ aggregate 10 requests
```

each instance tracks its own counters, so an aggregate limit of 5 is bypassed.
Redis (Upstash in production) is shared across all instances, so only the
Redis path gives true aggregate enforcement. In-memory state exists solely so
that a Redis outage **degrades protection instead of dropping it** or 500-ing
every request.

## Deployment guidance

- `main.py` enforces `workers=1` per container; the intended scale-out is
  **one Render service per role** (core/worker/scraper/mcp), each single-instance
  on the current free-tier topology — the in-memory fallback is acceptable
  there **only while Redis is down** (it is loud in the logs).
- If core is ever scaled horizontally, Redis MUST be reachable — otherwise
  rate limits become advisory per instance.
- All fallback activations log the phrase `EMERGENCY in-memory fallback`
  (RequestValidationMiddleware) or `Falling back to in-memory sliding window`
  (the other two layers). Alert on these phrases.

## Testing

- `backend/tests/core/test_security_rate_limit_backend.py` — Redis-authoritative
  allow/reject, critical-path overrides (login 5/600), fallback enforcement,
  per-instance isolation, stale-entry pruning.
- Both the two-phase fix (no zset refill on reject — prevents the
  self-amplifying 429 loop) and the `await` correctness of the fallback are
  locked by tests.
