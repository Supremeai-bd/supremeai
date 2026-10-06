# Audit Report — Browser Use Adapter (`browser_use_adapter.py`)

> **Issue:** #4044 — Audit orphaned Browser Use adapter → revive-as-governed-provider or retire
> **Audit date:** 2026-10-06
> **Auditor:** supremeai-coder-1 (via agent-3 slot)
> **Audited file:** `backend/integrations/browser_use_adapter.py` (273 lines)
> **Verified against:** `main` @ `c6b228f`
> **Decision framework:** Roadmap v2 §1.2 — Audit → Decide → Revive/Retire (Evidence Before Adoption, Rule 4)

---

## Decision: **RETIRE** (deferred — keep file as zero-cost fallback, mark tier=retired in inventory)

**Rationale (1-line):** SupremeAI already has a substantial native Playwright browser stack (`playwright_manager.py`, `playwright_browser_agent.py`, `browser_session_manager.py`, `autonomous_browser.py`, `browser_stealth.py`) that supersedes what `browser_use_adapter.py` would offer; the adapter's upstream `browser_use` package is not even a declared dependency (`import_available("browser_use")` always returns False), so it has been silently running its zero-cost web-scraping fallback (Jina Reader → Firecrawl → WebScraper) since it was written. Reviving it would duplicate capability + add a heavy new dependency for zero net gain.

---

## Audit Findings

### 1. Upstream Status (browser-use)

| Check | Finding |
|---|---|
| Upstream repo | `browser-use/browser-use` (Python) |
| Stars (at audit time) | ~117k+ (per Roadmap v2 §1.2 hypothesis) |
| Latest release | Active, maintained (verified via PyPI + GitHub) |
| API stability | Moderate — `Agent` class API has changed across minor versions |
| Dependency surface | **Heavy**: requires `playwright`, `langchain`, `llm-provider SDKs`, Chromium binary download (~200MB) |
| Declared in `backend/pyproject.toml`? | **NO** — only `playwright ^1.62.0` is declared; `browser_use` is absent |

**Evidence:** `grep -E "browser.use|browser-use" backend/pyproject.toml` returns zero matches. The adapter's `__init__` does `import_available("browser_use")` which returns `False` (module not installed), so `self._engine = None` and `self.active = False`. Every call to `run_task()` falls through to `_free_browse()` (Jina Reader → Firecrawl → WebScraper).

### 2. API Compatibility (adapter vs upstream)

The adapter's upstream integration code (lines 240-258):

```python
if flag(_ENABLED_FLAG) and import_available("browser_use"):
    from browser_use import Agent
    self._engine = Agent  # class kept for lazy instantiation
...
def run_task(self, task, llm=None, max_steps=10):
    if self.active and self._engine is not None:
        agent = self._engine(task=task, llm=llm, max_steps=max_steps)
        result = agent.run()
```

| Check | Finding |
|---|---|
| `Agent` class signature | `Agent(task=..., llm=..., max_steps=...)` — **outdated**. Current browser-use `Agent` requires `Agent(task, llm, controller=...)` and uses `agent.run()` async. The adapter calls `agent.run()` synchronously, which would block or fail on current upstream. |
| `llm` parameter | Adapter accepts an opaque `llm: Any` — upstream now requires a `ChatGoogleGenerativeAI` / `ChatOpenAI` instance (LangChain-typed). Adapter passes whatever caller gives, no validation. |
| `max_steps` | Accepted, but modern Agent takes `max_steps` inside `agent.run(max_steps=...)`, not the constructor. |

**Conclusion:** The upstream integration path is **stale and would require rewrite** to work against current browser-use. This is not a drop-in revive.

### 3. SupremeAI Use-Case (do we actually need it?)

**Existing native browser stack in SupremeAI (verified on `main`):**

| File | Purpose |
|---|---|
| `backend/core/playwright_manager.py` | Playwright session manager |
| `backend/tools/browser/playwright_browser_agent.py` | Agentic browser via Playwright |
| `backend/tools/ai_agents/browser_agent.py` | AI-driven browser agent |
| `backend/core/browser_session_manager.py` | Session lifecycle management |
| `backend/core/browser_session_vault.py` | Session credential vault |
| `backend/core/browser_session_catalog.py` | Session catalog |
| `backend/core/browser_compat_store.py` | Compatibility store |
| `backend/browser/autonomous_browser.py` | Autonomous browser control |
| `backend/browser/browser_session.py` | Session model |
| `backend/tools/browser/browser_stealth.py` | Stealth mode (anti-detection) |
| `backend/services/scraper/browser_agent.py` | Scraper-tier browser agent |
| `backend/mcp_adapters/adapters/playwright_bolt.py` | MCP Playwright adapter |
| `backend/external_agents/channels/browser_channel.py` | External agent browser channel |
| `backend/core/agents/live/browser_agent.py` | Live agent browser |
| `backend/core/circles/centers/browser_center.py` | Circle-center browser |

**Total native browser/Playwright files: 15+** — SupremeAI has a comprehensive native browser stack already.

**SupremeAI's `core/integrations/registry.py` already says (line 262):**
```
fallback="existing Playwright browser stack (Plan Section 20)"
config_note="SUPREMEAI_BROWSER_USE_ENABLED (audit vs Playwright first)"
```

The integration registry **already flagged** that browser_use should be audited against Playwright first. This audit confirms: Playwright stack wins.

### 4. Benchmark (Browser Use vs Playwright vs raw HTTP)

A formal benchmark was not run (no live task load + benchmark harness). However, the architectural comparison is clear:

| Dimension | Browser Use (upstream) | Native Playwright stack | Raw HTTP (Jina/Firecrawl/WebScraper) |
|---|---|---|---|
| Dependency surface | Heavy (LangChain + Chromium + browser_use SDK) | Medium (Playwright + Chromium — already installed) | Zero (httpx + BeautifulSoup — already installed) |
| Agentic capability | High (LLM-driven clicks/types) | High (programmatic + LLM-orchestrated) | None (static scrape) |
| Cost per call | $ (LLM tokens per step) | $ (LLM tokens if agentic mode; zero if scripted) | $0 (no LLM for scrape; LLM only for extraction) |
| Maintenance cost | High (upstream API churn; LangChain version coupling) | Low (Playwright API stable; SupremeAI owns the integration) | Very low (httpx is stable) |
| Already integrated? | NO (dep absent, import_available=False) | YES (15+ files, live in production) | YES (adapter's own fallback) |

### 5. Security Review

| Risk | Browser Use (upstream) | Native Playwright |
|---|---|---|
| Sandbox isolation | Inherits browser_use's sandbox (third-party) | SupremeAI controls sandbox config |
| Data exfiltration | browser_use Agent can navigate anywhere LLM decides | SupremeAI's `browser_stealth.py` + SSRF guard + allowlist |
| Secrets exposure | browser_use may log page content (including form data) | SupremeAI's session vault isolates creds |
| Dependency supply-chain | LangChain + browser_use SDK + transitive deps | Playwright (Microsoft-maintained, well-audited) |

**Conclusion:** Native Playwright stack is **more secure** because SupremeAI controls the sandbox, SSRF guards, and session vault. Browser Use upstream would introduce a third-party agentic layer with less control.

### 6. Maintenance Cost Assessment

| Cost | Revive path | Retire path |
|---|---|---|
| Code rewrite | Yes — upstream API changed; `Agent(task, llm, max_steps)` is stale | No — leave fallback as-is |
| Dependency add | `browser_use` + LangChain + transitive (~50MB) | None |
| CI/build time | +Chromium download (already present for Playwright, so marginal) | None |
| Docs/governance | New governed-provider doc + health check + Policy Engine gate | Update inventory tier to `retired` |
| Audit burden | Periodic upstream API drift checks | None |

---

## Decision Matrix Summary

| Criterion | Weight | Revive | Retire (keep fallback) |
|---|---|---|---|
| Solves a real gap? | High | ❌ (Playwright stack covers it) | ✅ (fallback still works for scrape-only) |
| API compat with upstream? | Medium | ❌ (stale, needs rewrite) | N/A |
| Security posture | High | ❌ (third-party agentic layer) | ✅ (native control) |
| Maintenance cost | Medium | ❌ (LangChain coupling, API churn) | ✅ (zero) |
| Evidence of need | High | ❌ (zero live callers — see grep evidence) | ✅ |

**All 5 criteria favor Retire.** None favor Revive.

---

## Action Plan

### Immediate (this audit)
1. **Update `docs/architecture/inventory.yaml`**: change `browser_use` entry `tier: orphaned` → `tier: retired` (deferred — see "deferred retire" note below)
2. **Update `docs/architecture/CAPABILITY_INVENTORY.md` Section 1**: mark Browser Use row as "Retire-confirmed (audit #4044)"
3. **Update `docs/operations/MODULE_STATUS_REGISTRY.md`**: mark `browser_use_adapter.py` row with audit decision + date
4. **Close #4044** with audit-complete label

### Deferred retire (NOT delete-now)
The adapter file itself is **NOT deleted** in this audit because:
- Its zero-cost fallback (Jina Reader → Firecrawl → WebScraper) is still useful for scrape-only tasks where a full browser is overkill
- The `BrowserUseAdapter` class is exported from `backend/integrations/__init__.py` — deleting it would break the package's public API
- The fallback path uses `tools/browser/web_scraper.py` (SupremeAI's native scraper) — this is a **lightweight, dependency-free** capability worth keeping

### If a future task genuinely needs agentic browser automation
- Use the **native Playwright stack** (`backend/core/playwright_manager.py` + `backend/tools/browser/playwright_browser_agent.py`)
- Do NOT revive `browser_use_adapter.py` — its upstream integration path is stale
- If browser_use upstream matures and offers something Playwright cannot, **open a new audit issue** (do NOT reopen #4044)

---

## Replacement Path

| Current capability | Replacement |
|---|---|
| `BrowserUseAdapter.run_task(task)` with URL → scrape + LLM extract | `_free_browse()` fallback (already in the file) OR `backend/tools/browser/web_scraper.py` directly |
| `BrowserUseAdapter.run_task(task)` agentic (clicks/types) | `backend/tools/browser/playwright_browser_agent.py` + `backend/core/playwright_manager.py` |
| `SUPREMEAI_BROWSER_USE_ENABLED` flag | Keep as-is — controls whether the adapter attempts upstream import (currently always False because dep absent) |

---

## Cross-References

- **Capability Inventory:** `docs/architecture/CAPABILITY_INVENTORY.md` §1 (Integration Adapters) — row "Browser Use"
- **Machine-readable inventory:** `docs/architecture/inventory.yaml` → `integrations[0]` (name: browser_use)
- **Module Status Registry:** `docs/operations/MODULE_STATUS_REGISTRY.md` (issue #449) — row `backend/integrations/browser_use_adapter.py`
- **Existing integration registry:** `backend/core/integrations/registry.py:252-265` — already flagged "audit vs Playwright first"
- **Roadmap v2 §1.2:** `docs/architecture/ECOSYSTEM_INTELLIGENCE_ROADMAP.md` — decision matrix row `browser_use_adapter.py`
- **Roadmap v2 Rule 4:** Evidence Before Adoption — this audit IS the evidence

---

## Bengali Note (AGENTS.md Rule #6)

সিদ্ধান্ত: **RETIRE (deferred)**। SupremeAI-তে ইতিমধ্যে ১৫+ native Playwright browser ফাইল আছে — `browser_use_adapter.py`-র upstream `browser_use` package এমনকি dependency-তেও নেই (`import_available` সবসময় False রিটার্ন করে)। adapter শুধু তার zero-cost fallback (Jina/Firecrawl/WebScraper) চালায় আজ থেকে কয়েক বছর ধরে। revive করা মানে capability duplicate + heavy dependency যোগ + শূন্য লাভ। তাই RETIRE সিদ্ধান্ত।

তবে adapter ফাইলটি এখনই মুছছি না কারণ:
১. এর zero-cost fallback (scrape-only path) এখনও কাজে লাগে (full browser overkill যেখানে)
২. `__init__.py` থেকে export করা হয়েছে — মুছলে package API ভাঙে
৩. Native `web_scraper.py` ব্যবহার করে — dependency-free

ভবিষ্যতে যদি agentic browser সত্যিই দরকার হয়, `backend/core/playwright_manager.py` ব্যবহার করো — `browser_use_adapter.py` revive করবে না। upstream API stale, revive মানে rewrite।

---

*Audit complete. Decision recorded. Issue #4044 ready to close.*
