# Maintainability Audit & Token-Efficiency Plan

**Date:** 2026-11-20 · **Branches:** `arena/974d6600-supremeai` (`decb51c`) + `arena/2b11b165-supremeai` (`17441cf`)
**Questions asked:** *how do we raise maintainability, find/fix real problems, and stop AI agents
burning tokens?* — and: *what is hardcoded that should be dynamic, and how much manual work remains?*

**Method:** measured, not read. Every number below is reproducible with the command shown.
The repo is 4,213 tracked files / 768k Python LOC — no human or agent can hold it in context,
so the findings that matter are the ones that make *navigation cheap* and *drift impossible*.

> **Companion audit (same date, separate session).** This document covers token-efficiency and
> structural drift. The section below — *Guard Enforcement & Latency* — covers execution
> reality: whether the guards listed above actually run, plus hardcoded-value and
> request-path findings. Both were measured independently on `17441cf`.

## G. Guard Enforcement & Latency (companion audit)

### G.1 🔴 The roster that "adopted" these guards is never executed

§1.2 above records the fix as *"roster entry added (`run_all_guards.py`)"*. That entry does
exist — but **no workflow invokes the roster**:

```
$ grep -rn "run_all_guards" .github/   → 0 hits
$ grep -c "run_all_guards" scripts/ci/run_all_guards.py → (defines GUARDS, 56 entries)
```

`make guards` runs it locally. CI does not. Direct consequence:

| Metric | Value |
|---|---|
| `scripts/ci/*.py` modules | **261** |
| reachable from any `.github/workflows/*.yml` | **38** |
| never invoked by CI | **223** |
| roster entries running `--self-test` **only** | **30** of 56 |
| roster entries running `--check` (the live check) | **20** |

A guard whose `--check` never runs is documentation, not a gate. `--self-test` verifies the
guard's own logic against fixtures — valuable, but it cannot detect that the repo is
currently violating the rule.

**Proven**, `scripts/ci/sprawl_guard.py`:
* absent from the roster entirely;
* `--check` exits **1** today with 4 real violations —
  `scripts/migrate_logging_imports.py`, `scripts/pre_push_shared.sh`,
  `scripts/setup_git_hooks.py`, `scripts/validate_schemas.py`.

**Also applies to the architecture guardian shipped in #706:**
`architecture_gap_guardian.py` has roster entries (lines 63–64), but the roster does not run,
and `tests/test_architecture_gap_guardian.py` is **not** in `config/ci/pr-battery.args`
(0 matches). The 6 real defects it found are therefore not protected against regression.

**Fix (highest value/effort ratio in either audit):** one workflow step invoking the fast
roster subset on PRs and the full roster nightly. ~1 hour, activates 56 guards.

### G.2 🔴 Duplicate routes — 8 real, currently silent

Method-aware (`METHOD+PATH`) and router-prefix-resolved. FastAPI keeps the **first** match and
silently discards the rest, so one handler per pair is dead code that still looks live:

```
GET  /skills          admin_routes.py:827        vs endpoints_command.py:251
POST /api/ci/webhook  ci_dashboard_api.py:273    vs ci_webhooks.py:12
GET  /health          health.py:67               vs scraper.py:67
POST /scrape          scraper.py:85              vs browser/_scraping.py:87
POST /browse          scraper.py:99              vs browser/_scraping.py:94
GET  /sessions        endpoints_crud.py:116      vs browser/_session_store.py:68
POST /security-scan   endpoints_security.py:16   vs browser/_crown_jewel.py:325
POST /admin-api/tenant-limits/{tenant_id}/reset  tenant_admin.py:362 (duplicate decorator)
```

⚠️ **Retracted measurement:** a first pass reported **97** duplicates. 89 of those were
`POST /rules` vs `GET /rules` — legitimate. Only the method-aware figure (8) is trustworthy.
Recorded so the wrong number is not reused.

### G.3 Latency: 21 middlewares per request

`core/app_builder.py` chains 21 layers on every request (added last = outermost, so
`OriginShield`/`ChaosInjector`/`Honeypot` run *before* auth):

```
CORS · RequestContext · DocsAuth · GZip · RequestId · SecurityHeaders · RequestValidation ·
TrustedOrigin · SupremeContext · TenantExtraction · Observability · QueryTiming · RateLimit ·
Idempotency · Auth · APIKeyAuth · AutonoGuard · Honeypot · ChaosInjector ·
ResponseStandardization · OriginShield
```

Six of these (`RequestId`, `RequestContext`, `SupremeContext`, `TenantExtraction`,
`SecurityHeaders`, `ResponseStandardization`) walk the same scope/response and can be folded
into one: **21 → ~8**. Plus path short-circuiting for `/health`, `/metrics`, static assets.
Estimated 1–3 ms/request saved (estimate — §G.6 explains why it is not yet measured).

**Already good, do not re-do:** `ServerTimingMiddleware` covers failure paths and is mounted
outermost (`gateway/service/app.py:607`); `GZipMiddleware(minimum_size=1000)` is present;
`QueryTimingMiddleware` instruments DB time; TTL/LRU caching in 16 modules. What is missing is
**aggregation** of Server-Timing into p50/p95.

Sync handlers: **194** `def` vs **654** `async def` in `core/api/routes`. FastAPI threadpools
sync handlers correctly, and most are CPU-light — only 2 showed blocking I/O in an AST pass
(`ecosystem_admin.py:514`, `admin_dashboard/__init__.py:112`). Not a defect class; convert
opportunistically.

### G.4 Hardcoded values ranked by payoff

| Rank | Hardcoded | Scale | Derive from | Impact |
|---|---|---|---|---|
| 🔴 1 | `render.yaml` service list | **3** declared | `config/service_registry.yaml` (**12**) | 9 of 12 services unmanaged by Render |
| 🔴 2 | model IDs in call sites | `gpt-4o-mini` ×**51**, `gemini-2.5-flash` ×34, `gpt-4o` ×24 | `core/brain/model_registry.py` + `gateway/routing_policy.json` (**both exist**) | model swap = 51 edits today |
| 🟠 3 | service names in code | 85 / 71 / 48 / 40 / 31 / 31 / 29 references | registry + env | rename touches dozens of files |
| 🟠 4 | route table | 8 collisions (§G.1) | derive at import, fail on collision | wrong-handler bugs |
| 🟡 5 | ports/hosts | `localhost:8000` ×34, `:3000` ×23, `:6379` ×20 | one `core/ports.py` | dev/prod drift |
| 🟡 6 | config modules | 10 siblings, `config_validation.py` (828 L) **and** `config_validator.py` (556 L) | one entry point | two validators, unclear authority |
| 🟢 7 | `_INDEX.md` | 885 lines / 74.9 KB | regenerate on commit + drift guard | covered by §1.3 |

**Not a problem:** 22 files matched a secret regex; the two sampled are test fixtures
(`"sk-do-not-print-123456"`, `"ghp_SUPERSECRET1234567890"`). No action — noted so it is not
re-investigated.

### G.5 Architecture guardian — remaining work

| Priority | Gap | Detail |
|---|---|---|
| 🔴 P0 | Not enforced in CI | roster never runs (§G.1) |
| 🔴 P0 | **No cycle detection** | `grep -c cycle` → 0. Circular imports are the top cause of cold-start stalls and partial-import `ImportError`s. |
| 🟠 P1 | 6 real defects open | §G.5.1 |
| 🟠 P1 | Route graph absent | It tracks modules, not endpoints → §G.2 invisible to it |
| 🟠 P1 | Middleware order absent | §G.3 order is load-bearing, human-checked only |
| 🟡 P2 | Global 38.1% only | No per-package unreachable ratio (`core/zero_cost_architecture` ≫ `gateway/`) |
| 🟡 P2 | 161 `unverified` never reconciled | should resolve against CI-injected installs |
| 🟡 P2 | Cold start unmeasured | import-cost table is one AST pass away |
| 🟢 P3 | `--json` has no schema | consumers cannot validate |

#### G.5.1 The 6 tracked defects (all verified absent on disk, all unguarded imports)

```
core.agents.governance.bias_detection_agent  -> core.llm.language_model
core.agents.governance.explainability_agent  -> core.llm.language_model
core.api.routes.pr_review_api                -> tools.pr_reviewer
scripts.ops.audit_underutilized_capabilities -> scripts.audit_isolated_components
scripts.ops.supreme_ops                      -> tools.tool_knowledge_injector
scripts.ops.verify_capabilities              -> core.evolution.self_evolution_agent
```

### G.6 Manual work that can be automated

| Manual step | Automate | Recurring saving |
|---|---|---|
| `make index` after adding a script | pre-commit + drift guard | removes a churn class |
| 20 `*baseline*.json` hand-refrozen | `refresh-baselines` rerunning all guards | highest-error chore |
| `render.yaml` hand-edited | generate from registry | 9 services |
| ruff `per-file-ignores` per directory | ratchet on count/severity | stops the slide |
| `CHANGELOG.md` by hand | derive from conventional commits | no stale changelog |
| 3 818 `except Exception` + 56 bare `except` | `audit_broad_exceptions.py` **already written, never runs** | capacity already paid for |
| duplicate-route discovery | import-time collision check | 8 today |
| model ID updates | registry routing | 51 → 1 |

**Several audits are already written and merely unscheduled** (`audit_broad_exceptions.py`,
`annotations_census_guard.py`, `check_hardcoded_deployment_config.py`, …). Registering them is
the cheapest available capacity.

### G.7 Order of work

1. **Wire the roster into CI** (Tier-1 subset + nightly full). Unlocks 56 guards + guardian.
2. Add `tests/test_architecture_gap_guardian.py` to `pr-battery.args`.
3. Register or delete the 110 orphan guard-like scripts; start with `sprawl_guard`,
   `audit_broad_exceptions`, `check_hardcoded_deployment_config`.
4. Guardian: cycle detection → route graph → per-package ratio → import-cost table.
5. Generate `render.yaml`; route model IDs through the registry.
6. Collapse 21 middlewares → ~8 with path short-circuiting.
7. `_INDEX.md` compaction; `refresh-baselines`; ruff ratchet.

### G.8 Limits of this companion audit

Static analysis + targeted greps, **not** runtime profiling — the 1–3 ms middleware figure is
an estimate. "110 orphan guard-like" is a heuristic (name keywords + flag presence); some are
libraries. Duplicate-route detection does not simulate `include_router` order, so "which
handler is dead" needs human confirmation per pair. The 194 sync handlers are mostly fine.

---

## 0. Scorecard

| Dimension | Measurement | Verdict |
|---|---|---|
| Repo size | 4,213 files · 768,447 py LOC · 24,631 md LOC | 🟡 large, but not pathological |
| Source spread | `core/` 150 root-level modules + 90 subpackages | 🔴 flat sprawl at the root |
| **Doc/instruction cost** | ~40k tokens just to *start* a session | 🔴 **biggest token sink** |
| **Mirror duplication** | 176 mirror groups, **107 drifted** | 🔴 worst structural problem |
| Exact duplicate files | 83 (only 757 LOC) | 🟢 not the issue |
| **Dead gates** | ≥1 config-SSOT guard crashed on every run | 🔴 false confidence |
| Lint gate | `E9,F63,F7,F82` only; ruff default `--statistics` ≈ 1,700 hits (advisory) | 🟡 acceptable ratchet, weak signal |
| Long functions | 55 >150 lines (worst: 1,868) | 🟡 contained |
| Test suite | 899 files / 194,862 LOC | 🟡 healthy volume |

**Root cause of all reds, in one line:** the repo has *more governance surface than verified
surface*. Guards, docs, plans and mirrors were added faster than they were wired, executed and
retired. Agents pay for that twice — once in tokens, once in wrong conclusions from stale files.

---

## 1. What I found (evidence)

### 1.1 🔴 The `scripts/` ↔ `scripts/ops/` mirror is the #1 maintainability defect

```bash
$ python3 scripts/ci/mirror_drift_guard.py   # tail
Total mirror groups: 176, drifted: 107
```

* 198 files under `scripts/ops/`, of which **102 have a same-path twin** at the `scripts/` root.
* Only **2** of those pairs are still byte-identical. **100 have diverged.**

`api_contract_diff.py` differs by trailing commas, `print()` vs `print("")`, and a
`dataclasses` import ordering; `backup_telegram.py` differs by a whole
`collect_docs_and_artifacts()` function. `info`-level divergence — which means **every read of
either copy silently teaches an agent the wrong file**. This is the most expensive failure mode
in the repo: an agent that reads `scripts/advanced_analysis/api_contract_diff.py` when CI runs
`scripts/ops/...` (or vice versa) burns a full context window and still gets it wrong.

Worse, the guard that catches this is **report-only** (`ops-maintenance.yml`, exit 0 always):

```yaml
- name: Mirror drift guard (report-only)
  run: python scripts/ci/mirror_drift_guard.py
```

So 107 drifts are *known, logged, and ignored* on a schedule.

### 1.2 🔴 The env/config SSOT contract was dead — fixed in this branch

`scripts/ci/generate_env_example.py` is the single generator that derives `.env.example` from
`core/config_classification.py::CONFIG_SPECS`. All three sibling guards share a locator
(`config_classification_locator.py`) that exists specifically because "both guards kept the old
path hardcoded — so both crashed with `FileNotFoundError` on every run and the only validators of
`config/service_registry.yaml` were effectively dead."

The generator was the **third** sibling and never got the fix:

```python
CLASSIFICATION = ROOT / "backend" / "core" / "config_classification.py"   # dir does not exist
```

`--check` died with `FileNotFoundError`; it was also the only one of the three **not wired into
`run_all_guards.py`**. Consequence, measured:

* **700** env vars are read in code but undocumented; **309** documented vars are never read.
* After the fix, the generator reports a precise, actionable backlog: **57** vars missing from
  `.env.example` — and `--check` now correctly exits 1 on that drift.

**Fixed (partially — see §G.1):** locator adopted + roster entry added (`run_all_guards.py`),
wiring-integrity guard re-verified PASS. This converts a silent `FileNotFoundError` into a
normal CI gate — *but only if the roster actually runs.* It does not: no workflow invokes
`run_all_guards.py` (§G.1), so the gate is currently local-only. The mechanism is correct; the
wiring to CI is still missing.

### 1.3 🔴 Session start-up costs ~40k tokens before any work

| File an agent is told to read | tokens |
|---|---|
| `AGENTS.md` (generated, 123 physical lines) | ~6,900 |
| `README.md` | ~4,045 |
| `ECOSYSTEM_MAP.md` | ~3,627 |
| `CONTRIBUTING.md` | ~3,279 |
| `scripts/ops/_INDEX.md` (990 rows) | ~21,905 |
| **Total** | **~40,400** |

Two aggravating factors:

1. `AGENTS.md` is **generated from `.github/constitution/rules.yml`** and packed into 21 lines
   *over 400 characters*. It is a 6,900-token wall with no section anchors an agent can jump to.
2. The real navigation asset (`scripts/ops/_INDEX.md`, 990 rows) is 22k tokens and is *itself*
   one of the drifted mirrors — it lists both `scripts/x.py` and `scripts/ops/x.py` rows.
3. 47 skills in `.agents/skills/` total **~89,000 tokens**. Nothing in `AGENTS.md` says which
   subset to load for which task, so agents either load none (and re-derive conventions) or too
   many (and drown).

Three competing "SSOT" plans (`MASTER_SIMPLIFICATION_PLAN.md`, `PROJECT_SIMPLIFICATION_MASTER_PLAN.md`,
`SYSTEM_WIRING_ATLAS.md`) make this worse: the plans disagree on purpose and an agent must read
all three to find out which one is current. 25 markdown files claim SSOT status.

### 1.4 🟡 Dead/false-confidence guards (not false green, but worth fixing)

* `check_hardcoded_deployment_config.py` has exception entries pinned to
  `backend/core/config_validation.py` / `backend/core/config_validator.py` — paths that no longer
  exist. Its own docstring promises `[discovery]` warn-and-skip, so it survives — but the
  exception is now protecting nothing. It is **not wired into CI at all**.
* `scripts/ci/audit_suite.py` still carries a full `backend/**` path-multiplier table.
* `generate_env_example.py` (before this fix) — see 1.2.
* Conclusion: *"guard exists"* does not imply *"guard runs"* or *"guard still protects"*.

### 1.5 🟡 The MCP Tower has no code-navigation tool

The Tower registers **144 tools across ~47 name families** (github 15, client 11, bridge 9,
slot 9, system 8, …). Its policy layer is *excellent* — `TOOL-EXPOSURE.md` documents a
`visible(tool) = RBAC-allows-call AND profile-allows-visibility` filter, list ⊆ call, fail-closed.

But for the question *"what breaks if I change this file?"* the surface is thin:

* **144 tools**, family naming is **inconsistent** — 132 dotted (`github.read_file`) + 12
  snake_case (`codebase_graph_query`, `devtools_audit`, `system_deep_diagnose`) that predate the
  2026-10-29/30 rename waves. `README.md` already warns agents to "never guess; probe
  `tools/list` first" — that warning is a *tax paid on every session*.
* Discovery is **profile-narrowed** (`chatgpt` ≈36 tools, `readonly` = that minus two writes), so
  a guest agent legitimately cannot see the repo-navigation tools it would need.
* `codebase_graph_query` **requires a pre-built `graph.json`** (`findGraphJson()` → returns
  "graph not found" otherwise). There is no build step in the repo that guarantees it exists, so
  the tool is usually a dead end.
* The graph itself is deliberately truncated by `.graphifyignore` ("strictly under 8,000 nodes"),
  excluding `vscode/`, `browser/`, frontend, `*.tsx` — i.e. **it cannot answer impact questions
  for a large share of the tree it claims to cover**.
* There is **no tool that returns "who imports / who calls X"**. `core/api/routes/code_dependency_graph.py`
  exists as a route, but it is not exposed through Tower.

**Verdict on the Tower: very helpful for *operations* (health, deploy, PR/bridge workflow,
release evidence, presence). Not currently helpful for *codebase navigation*, which is where the
tokens actually go.** The gap is one tool, not a redesign — see Pillar 3.

---

## 2. Plan — four pillars, ordered by (tokens saved ÷ risk)

The ordering is deliberate: each pillar makes the next one cheaper, and every step is verifiable
by an existing guard.

### Pillar 1 — Kill the mirror (30–40% of all agent confusion)

**P1.1 · Decide one canonical tree and delete the other (blocking).**
`scripts/ops/` was introduced as a reorganisation but nothing ever completed it. Pick by evidence,
not preference:
* CI references **both** (`scripts/ops/wiring_atlas.py` ×6, `scripts/ops/feature_parity_sentinel.py` ×2,
  `scripts/ci/*` ×~60).
* `scripts/ops/_INDEX.md` and `generate_script_index.py` assume the full tree under `scripts/`.
* Recommendation: **canonical = `scripts/` root paths as CI already invokes them; delete the 100
  drifted `scripts/ops/` twins, keep the ~96 `scripts/ops/`-only files (they are the real
  reorganisation cohort).** That keeps every existing CI invocation valid and removes all
  ambiguity.
* Do it in **one PR, generated not hand-edited** (`scripts/ci/plan_duplicate_refactors.py` already
  exists and is currently unreferenced — wire it into the PR lane as the generator/evidence).

**P1.2 · Make the ratchet bite.** Once drift is 0, split the guard into two modes so it can never
silently rot again:
* `mirror_drift_guard.py --strict` → **fail** on new drift (PR lane, `--max-new 0` like
  `detect_new_duplicates.py` already does).
* keep report-only only for the *legacy* cadence lane.
Update `_INDEX.md` so it lists **one row per script** (this alone removes ~450 rows / ~10k tokens).

**P1.3 · Add a one-question-onboarding doc.** `docs/INDEX.md` classifies every doc as
`current | reference | historical`. Add `status:` front-matter to the three competing plans and
mark exactly one as `current`. Guard: extend `docs_link_integrity_guard.py` to fail on two
`status: current` plans.

### Pillar 2 — Make the agent's first 30k tokens unnecessary

**P2.1 · `AGENTS.md` → router, not encyclopedia (highest ROI, lowest risk).**
Split the generated output into `AGENTS.md` (a ≤150-line **decision table**: "if you touch X, read
Y") plus `docs/agents/CONSTITUTION.md` (the full rules). `generate_agents_md.py` already exists and
is CI-drift-checked, so this is a generator change + one template. Target: **6.9k → ~1.5k tokens**,
with the rest loaded on demand.

**P2.2 · Skill selection table.** Add to the new router: `task → skills[] → est. tokens`, so an
agent loads 1–2 of the 47 skills (~89k tokens total) instead of guessing. Guard:
`skill_conformance_guard.py` already exists — extend it to require every skill appear exactly once
in the table.

**P2.3 · Ship a code map as a *generated artifact*, not a chat read.**
Pillar 3 depends on this: emit `docs/generated/REPO_MAP.json` (file → symbols → imports →
imported-by, plus owning service from `config/service_registry.yaml`) and a 40-line
`REPO_MAP.md` index. One artifact unlocks the navigator and makes `.graphifyignore`'s 8k-node
limit irrelevant. Keep it **out of Git** (external-storage convention) unless it stays <1 MB.

### Pillar 3 — Close the Tower's navigation gap (this is where "will it be helpful?" gets answered)

**Your Tower is already valuable — for operations. Add exactly one family, `code.*`, and it
becomes the token-efficiency engine for coding agents.** All of these are read-only and fit the
existing `visible(tool) = RBAC ∧ profile` invariant without a policy change:

| New tool | Answers | Replaces (agent tokens burned today) |
|---|---|---|
| `code.impact(file, symbol?)` | who imports/calls this; affected services | 5–15 `grep`/read round-trips |
| `code.search(pattern, glob, k)` | ranked symbol search, `file:line` only | `github.search_code` + full-file reads |
| `code.snippet(path, symbol)` | the function body, not the 600-line file | 1 full-file read (usually 10–20k tokens) |
| `code.map(service?)` | the generated `REPO_MAP.json` slice | reading 4 orientation docs (~18k tokens) |

Three non-negotiable implementation notes:
1. **Serve snippets, never files.** Every response carries `file:line` + a budget cap; the agent
   decides whether to ask for more. This is the single biggest token lever after Pillar 1.
2. **`code.map` must read the artifact from P2.3**, not build it per call — no `graph.json`
   prerequisite, no 8k-node ceiling.
3. **Do not add these to the `chatgpt` profile's tool list blindly** — they are safe (read-only,
   repo-scoped) and belong in `readonly` too; leaving them out recreates the discovery/authorization
   mismatch `TOOL-EXPOSURE.md` §1 was written to kill.

**P3.2 · Fix the naming tax.** Finish the rename wave for the 12 surviving snake_case tools
(`codebase_graph_query`, `devtools_audit`, `system_deep_diagnose`, `orchestrator_dispatch`, …) to
dotted families, with the existing `test_tool_tombstones.ts` pattern keeping aliases as tombstones
for one release. Then `README.md`'s "never guess; probe `tools/list` first" caution can be deleted —
that paragraph alone is ~200 tokens of pure apology for an avoidable inconsistency.

**P3.3 · Publish `tools/list` budgets.** Cap advertised schema size per profile (the `chatgpt`
profile at ~36 tools is already the right shape). Add the equivalent "narrow profile" for coding
agents (`coder` ≈ 12 tools: `code.*` + github read + bridge). One profile = one small prompt.

### Pillar 4 — Turn governance into *verified* governance

**P4.1 · "Guard exists" → "guard runs".** Add a meta-guard: every `scripts/ci/*_guard.py` must
appear in `run_all_guards.py` or in a dated `report-only` allowlist with a reason. `wiring_integrity_guard.py`
already validates the *roster*; this validates the *inverse* (a guard nobody runs).

**P4.2 · Fix the stale-path class once.** Replace the remaining `backend/**` literals
(`check_hardcoded_deployment_config.py`, `audit_suite.py`) with the shared locator pattern, and
add `--discovery` output as a failing mode so an exception protecting a non-existent file is loud.

**P4.3 · Close the 57-var env backlog.** With the generator live, regenerate `.env.example` and
delete the 309 unread vars. Guard already added — it will hold the line from here.

**P4.4 · Lint ratchet (last, deliberately).** Only after Pillar 1 lands: enable `I001` + `F401`
(fixable, ~140 sites) and `BLE001` (202) as a **ratchet on changed files only**. Do not attempt a
repo-wide cleanup — that is exactly the "big rewrite" the simplification plans (correctly) warn against.

---

## 3. Sequence and expected effect

| Step | Work | Risk | Effect |
|---|---|---|---|
| 0 | **Done in this branch:** env generator fixed + wired | none | 1 dead gate → live; 57-var backlog visible |
| 1 | P1.1–P1.2 mirror kill (generated PR) | medium (CI paths) | **−100 ambiguous files**, `_INDEX.md` −45%, drift 0 and ratcheted |
| 2 | P2.1–P2.2 AGENTS router + skill table | low | **−5.4k tokens/session**, deterministic skill loading |
| 3 | P2.3 + P3.1 `REPO_MAP` + `code.*` tools | medium | **replaces most grep/read round-trips**; biggest ongoing savings |
| 4 | P3.2–P3.3 naming + `coder` profile | low | removes the "probe `tools/list`" tax every session |
| 5 | P4.1–P4.3 verified governance | low | stops the next generation of dead gates |
| 6 | P4.4 lint ratchet | low | slows re-rot |

**Why this order:** step 1 must precede 3 — a navigator over a tree with 107 contradictory twins
would confidently return the wrong answer, which is worse than no navigator. Step 2 is free and can
land immediately. Nothing here is a rewrite; every item extends a generator, guard, or tool that
already exists in the repo.

---

## 4. Answers to the two questions you actually asked

**"Will the MCP Tower be helpful?"**
Yes — for *operations*, it is already the strongest asset in the repo (health, deploy attestation,
PR/bridge workflow, release evidence, presence, and a well-designed tool-visibility policy). For
*maintainability and token burn*, it is currently **not** helpful, because it has no tool that
answers "what does this change touch?" — and that is precisely the question coding agents spend
their tokens on. **One new `code.*` family (Pillar 3) turns the Tower from an ops console into the
token-efficiency engine.** That is a ~200-line addition riding on an artifact (P2.3) that costs one
generator — not a redesign.

I could not reach `https://supremeai-mcp-tower-live.onrender.com/mcp` from this sandbox (egress is
restricted to GitHub/npm/PyPI; the host resolves but connections are blocked), so the Tower analysis
above is from source (`infrastructure/mcp-control-plane/src/`, 173 TS files / 35,175 LOC) rather
than from a live `tools/list` probe. The tool counts are derived from the `server.tool` /
`server.registerTool` call sites, which is the same set `registerAllTools` advertises.

**"What should we fix first?"**
The mirror (Pillar 1). It is the cheapest fix with the largest effect, it is already detected by a
guard you own, and until it is gone every other navigation improvement will hand agents the wrong
file with high confidence.

---

## 5. Reproduce

```bash
python3 scripts/ci/mirror_drift_guard.py                       # 176 groups, 107 drifted
python3 scripts/ci/generate_env_example.py --check             # now exits 1: 57-var backlog
python3 scripts/ci/wiring_integrity_guard.py --check           # roster verified incl. new entry
python3 scripts/ci/docs_link_integrity_guard.py                # link ratchet (holds)
```

Changes in this branch: `scripts/ci/generate_env_example.py` (shared locator),
`scripts/ci/run_all_guards.py` (env SSOT contract wired), this document.
