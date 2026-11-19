# Provider Core Hardening — 2026-11-19

**Scope:** the chat/provider path (`gateway/`), the landing pipeline
(`.github/workflows/unified-pipeline.yml`), and the guards that keep both
honest. Every item below is a code change already on this branch, with the
failure it removes. Manual/console work is listed separately at the end —
nothing in that list is fixable from the repo.

Base commit: `bea2978` ("fix(ci): remove manual production environment gate
from auto-deploy jobs").

---

## 0. The finding that mattered most: every MCP gate was dialing a dead host

`supremeai-mcp-tower.onrender.com` is **suspended** (owner action). The
canonical control plane — verified live on 2026-11-19, `GET /health/live` →
`{"status":"ok","live":true}` — is
`supremeai-mcp-tower-live.onrender.com`.

`bea2978` had silently reverted that hostname in 34 runtime files, while
`config/service_registry.yaml` and `render.yaml` still carried the retired
name. Effect: `mcp.json`, ~25 CI watchdogs/probes, the fleet-health entry in
`gateway/service/app.py`, the Cloudflare keepwarm worker and the studio proxy
all handshook with a suspended service, and the registry — the SSOT everything
else is supposed to copy — advertised it.

Fixed by: bulk repoint to `-live` (0 stale references remain outside `docs/`),
SSOT rename in `config/service_registry.yaml` + `render.yaml`, a
`production_url` on the registry entry, and a **guard** so the class cannot
come back (see §6).

---

## 1. Circuit breaker: built, tested, and previously never called

`gateway/circuit_breaker.py` existed with zero callers, and
`execute_chain(..., circuit_breaker=...)` accepted the argument and ignored it.
A provider that was down cost the full transport timeout on *every* request.

Now (`gateway/provider_chain.py::execute_chain`):

| behaviour | detail |
| --- | --- |
| skip open providers | `allow()` is consulted before the transport; a skipped route writes an `outcome="circuit_open"` ledger entry so the 502 body still explains itself |
| record outcomes | `record_failure` on transport error and on 5xx/401/403; `record_success` on `<400` |
| honest 4xx passthrough | a provider-shaped 400 is *not* a health failure and does not trip the breaker |
| **fail-open** | if every route in the chain was skipped by the breaker, the chain is retried once with `circuit_breaker=None` — a stale breaker can never manufacture a 502 |

`gateway/main.py` now builds **one breaker per app** (`create_app`) and exposes
it at `app.state.circuit_breaker`, so two apps in one process never share
cooldown state.

Regressions: `gateway/tests/test_circuit_breaker_wiring.py` (skip-without-
transport, fail-open, success-resets, per-app ownership).

## 2. Unbounded request bodies (memory + bandwidth)

`/v1/chat/completions` called `await request.json()` with no ceiling, so one
client could buffer an arbitrarily large body into a 512 MB container (OOM kill
of the public API, not a 413) and bill the bytes on Render.

`gateway/main.py` now reads through `_read_limited_body()`: `Content-Length` is
a fast reject, chunked bodies are abandoned the moment they cross the cap, and
`messages` count is capped separately. Knobs:
`GATEWAY_MAX_REQUEST_BYTES` (default 1 MiB), `GATEWAY_MAX_MESSAGES`
(default 200). Errors are the standard JSON contract
(`413 request_too_large`, `400 too_many_messages`).

## 3. Infisical vault: a 20-second blocking call inside `async def`

`gateway/service/admin_auth.py::get_vault_secret` runs a two-step
Infisical login+fetch (2 × 10 s timeout) synchronously, and it was called from
`async def` admin handlers. One cold vault stalled the whole event loop, i.e.
every chat request.

Now: TTL cache (`INFISICAL_CACHE_TTL`, default 300 s), short negative cache
(`INFISICAL_MISS_TTL`, default 30 s — an unset secret used to re-login on
*every* request), a `threading.Lock` for single-flight, values this module
promotes into `os.environ` are tracked in `_vault_promoted` so the TTL is not
silently defeated, and `get_vault_secret_async()` / `await
_supabase_base_url()` run the blocking part off the loop
(`asyncio.to_thread`).

Regressions: `gateway/tests/test_admin_vault_cache.py`.

## 4. Landing decision: advisor wired, downgrade-only

`scripts/ci/ai_pr_evaluator.py` (Value/Safety engine, 1 350 lines) was never
consulted by the pipeline. Wiring it as an equal would let a heuristic widen
its own blast radius into an auto-merge.

`scripts/ci/landing_decision_compose.py` defines the only permitted rule —
the trusted-base `tiny_brain_pr_guard.py` decides; the advisor may turn
`AUTO_MERGE` into `OWNER_REVIEW`, never the reverse, and any advisor failure
(crash, timeout, unparsable output, `PENDING`) is a no-op. Wired into
`.github/workflows/unified-pipeline.yml` (`ai-evaluate-and-approve`, fail-open
by design). Regressions: `tests/ci/test_landing_decision_compose.py`.

## 5. Deploy/approval split is now an invariant, not a comment

Exactly one job may carry `environment: production`: `auto-merge-high-risk`,
the owner-review gate. Gating a deploy job re-introduces a human approval on
every merge and stalls auto-deploy (the regression `bea2978` fixed);
un-gating the review job lets protected changes land on CI signal alone.
`tests/ci/test_deploy_environment_split.py` pins both directions, plus
"decision runs from the trusted base commit" and "the gate cannot merge".

## 6. Guards — make the classes un-reintroducible

- `scripts/ci/ghost_host_guard.py` generalized from one retired host to a
  **list** of retired hosts (`ghost host`, `suspended Tower host`), each with
  its own banner marker, evidence-lane allowance, and zero-tolerance rule for
  executable/config surfaces. Its self-test now proves 13 scenarios, including
  "one target's banner cannot whitewash another target".
  *It was already red on `main`*: `core/tests/core/test_allowed_hosts_policy.py`
  asserted the ghost host as its fixture — fixed to the live host.
- `scripts/ci/tiny_brain_pr_guard.py`: provider core is now owner-review
  surface — `gateway/provider_chain.py`, `gateway/circuit_breaker.py`,
  `gateway/routing_policy.json`, `gateway/config.py`, `gateway/main.py`,
  `gateway/service/providers/{adapters,pool}.py`.
- `config/ci/pr-battery.args`: the breaker + transport/limit suites run on
  every PR.

## 7. CI: keepwarm, image supply chain, CVE coverage

- `.github/workflows/keepwarm.yml` was pinging only the CF mesh + gateway, so
  a suspended Tower again would have been invisible until a client broke.
  It now probes **every** registry service with a `production_url` in parallel,
  fails loudly on `api`/`mcp` (the two that serve users and every MCP gate),
  and derives hosts from `config/service_registry.yaml` instead of re-typing
  them.
- `.github/workflows/gateway-image.yml` (new): builds `gateway/Dockerfile` on
  GitHub minutes, publishes `ghcr.io/<owner>/supremeai-gateway:sha-<sha>` +
  `:main`, and Trivy-scans the exact image it built (SARIF → Security tab).
  Render currently rebuilds that image on every deploy; those build minutes are
  what exhausted the free-tier quota. Switching Render to the published image
  is a one-line blueprint change plus a registry credential (manual, §8).
- `.github/workflows/container-security.yml` (new): the Trivy contract that
  `scripts/ci/security_gate.py` had documented for itself but nothing executed,
  now running against the lockfiles. Both scans are report-only stage 1
  (`exit-code: 0`) so the first run is a baseline; promoting them to blocking is
  a one-line change once the baseline is clean.

## 8. Dead code, made deliberate

`core/llm/top_ai_detector.py` (191 lines) duplicates the provider-health policy
that §1 just wired for real, and has zero production importers. It is marked
`.. deprecated::` with the reason, and
`tests/test_top_ai_detector_deprecation.py` fails if anything in production
starts importing it — so the "adopt or delete" decision has to be made on
purpose.

`pytest.ini`: `asyncio_default_fixture_loop_scope = function` — pytest-asyncio
warned on every run and plans to change the default, which would silently move
fixture-loop sharing in every async test.

---

## Manual / console work (not fixable from the repo)

| item | why it still matters |
| --- | --- |
| Create the GitHub `production` **environment with a required reviewer** | the one remaining `environment: production` gate is a no-op until the environment exists |
| Delete/rename the suspended Tower service in Render; confirm `RENDER_MCP_SERVICE_ID` targets `-live` | the dead service still exists in the dashboard and can be re-selected |
| Add the GHCR registry credential to Render | prerequisite for deploying the pre-built image instead of rebuilding (§7) |
| Verify `MCP_API_KEY`, `MCP_ADMIN_KEY`, `SUPREMEAI_API_KEY_*`, `SELF_HEAL_PAT` | guards fail closed, so a missing key reads as "gate red", not "not configured" |
| Reconnect the GitHub App (`brain`) with its permissions, renew the Harness Delegate token | CI-side integrations silently 403 otherwise |
| Promote the CVE scans from report-only to blocking once the baseline is clean | closing the loop on §7 |
