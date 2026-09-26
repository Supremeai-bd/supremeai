# Platform-Agent Charter (agent-11)

> **Issue:** [#1439](https://github.com/SaifulHaqueNiloy/supremeai/issues/1439) (ecosystem plan) · role-based assignment PR #1443
> **Owner slot:** `agent-11` — `AGENT_SLOT_REGISTRY.yaml` (source of truth)
> **Automated sweep:** `.github/workflows/platform-agent-check.yml` (cron `0 */3 * * *` + manual `workflow_dispatch`)

---

## Mission

agent-11 **owns every 3rd-party platform this project touches, end-to-end**:

1. **Check** — every 3 hours, all connected platforms are probed with their real
   API keys (not synthetic pings).
2. **Report** — any problem (auth failure, quota exhaustion, degradation,
   drift between vault and reality) becomes a GitHub issue with the
   `handoff:platform` label.
3. **Fix** — if the fix lives in OUR repo (adapters, pool init, env wiring,
   failover logic), agent-11 fixes it on `agent-11/<task>` branches.
4. **Platform-side changes** — if the fix lives on the PLATFORM side (rotate a
   token, change a plan/quota, re-enable an API, env-var changes on a vendor
   console or Render service), agent-11 prepares and applies it — destructive
   or billing-affecting changes get owner approval first (see §Escalation).

**Rule (handoff orchestration):** *role owns responsibility, orchestrator owns
routing, GitHub owns events, Merge Guardian owns merge.*

---

## Platform inventory (check every 3 hours)

| # | Platform | Probe (per 3h sweep) | Keys source | Notes |
|---|---|---|---|---|
| 1 | Render (tower, primary, worker, scraper) | `GET /v1/services` + latest deploy status per key | `RENDER_API_KEY_1..4` (Actions secrets) | 4 accounts, service↔key map documented in ops runbook |
| 2 | Upstash Redis chain (primary→quinary) | REST `PING` on each of the 5 accounts | Infisical pull in workflow | Primary 500k/day ceiling — see [#1438](https://github.com/SaifulHaqueNiloy/supremeai/issues/1438), [#1430](https://github.com/SaifulHaqueNiloy/supremeai/issues/1430) |
| 3 | MCP control tower | MCP `initialize` handshake + `health_check` tool | `MCP_API_KEY` / `MCP_ADMIN_KEY` (Infisical) | URL: `RENDER_MCP_URL` |
| 4 | Infisical vault | Universal-auth login (the pull itself is the probe) | `INFISICAL_CLIENT_ID/SECRET` | If this fails, mark all dependent probes as UNKNOWN, not DOWN |
| 5 | Cloudflare | `GET /client/v4/user/tokens/verify` per token | `CLOUDFLARE_API_TOKEN` + Infisical multi-account tokens | secondary-5 token history — degraded before |
| 6 | Supabase | `GET {url}/auth/v1/health` | Infisical (`SUPABASE_URL`, anon/service keys) | SUPABASE_KEY unauthorized history — #1391 |
| 7 | Kaggle | Basic-auth `GET /api/v1/competitions/list` | Infisical (`KAGGLE_API_TOKENS` pool) | lazy-pool init fix already on main |
| 8 | AI providers (Groq, Cerebras, OpenAI, Gemini) | Cheap `GET /models` per key | Infisical | Current known-bad: #1378/#1379/#1380/#1381 — re-probe before assuming |
| 9 | Firecrawl | `POST /v1/team/credit-usage` | Infisical | Free-tier credits — #1390 |
| 10 | GitHub | `GET /rate_limit` (always available in Actions) | `GITHUB_TOKEN` | Baseline — if this fails, the runner itself is broken |

**Sweep budget:** ~25–35 API calls per run, 8 runs/day → well inside every
provider's free tier. Upstash cost: 5 PINGs × 8 = 40 commands/day (negligible
vs the 500k ceiling).

---

## Check protocol

1. **Automated sweep (every 3h):** workflow runs the probe matrix, writes a
   timestamped summary to the job summary, and on any DOWN/degraded result
   opens or updates a tracking issue (see §Issue protocol).
2. **Deep audit (weekly or on-demand):** full env audit per Render service
   (snapshot → union → diff-verify protocol), vault↔registry drift check
   (#1392), quota/usage trend for Upstash + AI providers.
3. **Vault is the source of truth.** A probe that fails with a key that Infisical
   says is valid = platform problem. A probe that fails because the key is
   missing/revoked in Infisical = vault-drift problem (#1392).

---

## Issue protocol

- **Label:** `handoff:platform` (routes to platform-agent in the handoff
  orchestration schema — `docs/agents/handoff-orchestration.md`).
- **Dedup:** the automated sweep searches open issues with the same
  `[platform-agent]` title prefix before creating a new one — existing issue
  gets a timestamped comment instead of a duplicate.
- **Severity:** `critical` = production chain broken (all Redis accounts, all
  Render services, Infisical unreachable). `high` = single primary platform
  degraded. `medium` = secondary account / one provider key bad.
- **Every issue must contain:** platform, probe method, exact error, key
  source (which vault path / secret name), and a "manual action needed?"
  verdict.

## Fix protocol

1. Branch: `agent-11-<task>` off latest `main` (hyphen form — the slash form
   `agent-11/<task>` is impossible while the `agent-11` registration branch
   exists, git refuses the directory/file ref conflict; never work on the
   stale `agent-11` registration branch itself).
2. Fix in-repo (adapter, pool, env wiring, failover) → normal PR flow.
3. Platform-side config change:
   - **Non-destructive** (add env var via safe snapshot→union→diff-verify PUT,
     rotate a token we own, re-run a deploy): agent-11 applies directly,
     documents in the issue.
   - **Destructive / billing** (delete resource, upgrade plan, wipe data,
     change quota-affecting settings): draft the exact change in the issue,
     `@SaifulHaqueNiloy` approval required before applying.
4. Max 3 retries per task, then escalate (handoff orchestration safety rule).

## Escalation

| Situation | Action |
|---|---|
| Key revoked/expired on vendor console (OpenAI/Gemini/Groq/Cerebras/Supabase/Google) | Issue with `manual action needed` verdict — owner must rotate in vault |
| All 5 Upstash accounts failing | `critical` issue + check #1430 for primary quota |
| Infisical unreachable | Freeze probes as UNKNOWN, `critical` issue — no data changes until restored |
| Merge/deploy needed for a fix | Standard PR flow; Merge Guardian (agent-8 policy) owns merge |

---

## References

- Handoff schema: `docs/agents/handoff-orchestration.md`
- Heartbeat integration: `docs/agents/heartbeat-integration.md`
- Slot registry: `docs/master_docs/AGENT_SLOT_REGISTRY.yaml`
- Registry persistence: #1421 · Upstash load roadmap: #1438 · Primary quota: #1430
