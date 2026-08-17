# Implementation Plan: Needle 2 Architectural Adoption in SupremeAI

> **Status:** Review-complete, implementation-ready
> **Author:** Kilo (Principal AI Engineer)
> **Created:** 2026-08-18
> **Phase:** Development Phase (per AGENTS.md)

---

## TL;DR — What Changes & Why

The original Needle 2 plan proposed a standalone `CloudConfidenceGate` class. After auditing the codebase, this is **redundant** with 3 existing routing layers (`AdvancedModelRouter`, `LatencyAwareWeightedRouter`, `PerformanceOptimizer`). This plan **consolidates** the confidence gate into the existing `AdvancedModelRouter` and adds two genuinely missing capabilities: tiered fast-path bypass and multi-needle cross-reference scoring.

### Three atomic features

| # | Feature | Files Changed | New or Modify |
|---|---------|---------------|---------------|
| 1 | **Tier 0 Fast-Path** (confidence gate + deterministic execution) | `core/llm/advanced_model_router.py`, `core/llm/llm_gateway.py` | Modify existing + 1 new method |
| 2 | **Structured Skill Input Validation** | `core/skills/base.py`, `core/skill_manager.py` | Modify both |
| 3 | **Multi-Needle Context Retrieval** | `services/memory_service.py`, `core/unified_memory.py`, `api/routes/unified_memory_api.py` | Modify all three |

---

## Architecture: Where Each Tier Lives

```
                     ┌─────────────────────────────────────────────┐
                     │  LLMGateway.acompletion() (llm_gateway.py:393)│
                     └──────────────┬─────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ AdvancedModelRouter (NEW       │
                    │   .route_with_confidence())    │
                    └──────┬──────────────────┬─────┘
           ┌───────────────┘                  └───────────────┐
 Tier 0    │  confidence >= 0.85 + is_deterministic=True      │ Tier 1/2
 (Zero     │  → execute_deterministic()                       │ (LLM call)
  Cost)    │  → returns JSON immediately, no litellm call     │ → _build_call_chain()
            │                                                  │ → fallback chain
            └──────────────────────────────────────────────────┘
```

The existing `analyze_prompt_complexity()` method (advanced_model_router.py:76) already returns `{"length", "complexity", "overall"}` as 0-1 floats. **We reuse `overall` as the confidence score** — no new computation needed.

---

## Atomic Task Breakdown

### Task 1: Add Tier 0 Fast-Path to AdvancedModelRouter

**Pre-Flight Check (5Q):**
1. ✅ Already done? — `analyze_prompt_complexity()` exists (line 76) but never short-circuits; LLM call always happens.
2. Files: `core/llm/advanced_model_router.py` (modify)
3. Verify: `tests/test_confidence_gate.py` — prompt `"List Python files in /tmp"` returns deterministic result, no litellm call
4. Side effects: `LLMGateway.acompletion()` (line 444) calls `optimize_model_selection` — need to hook before `_build_call_chain` (line 446)
5. Single commit: yes

**Changes to `core/llm/advanced_model_router.py`:**

Add a `route_with_confidence()` method and a deterministic execution dispatcher:

```python
# At module level — deterministic task patterns (pure Python, zero-cost)
_DETERMINISTIC_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("list_files", re.compile(r"list\s+(?:all\s+)?(?:files?|py|js|ts)\s+(?:in|under)?", re.I)),
    ("regex_format", re.compile(r"format\s+as\s+(?:json|xml|csv|table)", re.I)),
    ("schema_lookup", re.compile(r"(?:show|list|describe)\s+(?:schema|tables?|columns?)", re.I)),
    ("pypi_search", re.compile(r"search\s+(?:pypi|pypi\s+for)\s+", re.I)),
]

@dataclass
class ConfidenceDecision:
    confidence: float
    is_deterministic: bool
    task_type: str
    matched_pattern: str | None
    deterministic_result: dict[str, Any] | None

class Tier0Dispatcher:
    """Zero-cost deterministic executors for high-confidence tasks.
    Runs BEFORE any LLM API call — no token consumption, no latency."""

    @staticmethod
    def execute(pattern_name: str, prompt: str) -> dict[str, Any]:
        # Implementation per pattern — see below
        ...
```

Add `route_with_confidence()` to `AdvancedModelRouter`:

```python
def route_with_confidence(self, prompt: str, task_type: str = "general") -> ConfidenceDecision:
    """Single entry point: complexity score + deterministic pattern matching.
    Replaces the caller's need to invoke both analyze_prompt_complexity AND
    a separate gate."""
    complexity = self.analyze_prompt_complexity(prompt)
    confidence = complexity["overall"]

    matched = None
    for name, pattern in _DETERMINISTIC_PATTERNS:
        if pattern.search(prompt):
            matched = name
            # Boost confidence for exact pattern match
            confidence = max(confidence, 0.85)
            break

    is_deterministic = matched is not None and confidence >= 0.85

    result = None
    if is_deterministic:
        result = Tier0Dispatcher.execute(matched, prompt)

    return ConfidenceDecision(
        confidence=confidence,
        is_deterministic=is_deterministic,
        task_type=task_type,
        matched_pattern=matched,
        deterministic_result=result,
    )
```

**Tier0Dispatcher.execute() implementations:**

```python
class Tier0Dispatcher:
    @staticmethod
    def _search_pypi(query: str) -> dict[str, Any]:
        """Pure-stdlib HTTP call to PyPI JSON API. Zero LLM cost."""
        import urllib.request, json
        # Extract package name from "Search pypi for pandas" → "pandas"
        pkg = re.search(r"(?:pypi\s+for\s+|pypi\s+)(\S+)", query, re.I)
        pkg_name = pkg.group(1) if pkg else query.strip()
        url = f"https://pypi.org/pypi/{pkg_name}/json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SupremeAI/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return {
                "name": data["info"]["name"],
                "version": data["info"]["version"],
                "summary": data["info"]["summary"],
                "home_page": data["info"]["home_page"],
            }
        except Exception as e:
            return {"error": str(e), "query": pkg_name}
```

### Task 2: Integrate gate into LLMGateway.acompletion()

**Changes to `core/llm/llm_gateway.py`:**

Insert the bypass check at line 444 (after `optimize_model_selection`, before `_build_call_chain`):

```python
# After line 444: model = await self.performance_optimizer.optimize_model_selection(...)
# BEFORE line 446: call_chain = self._build_call_chain(...)

# ── Tier 0 Fast-Path: bypass ALL LLM calls for deterministic tasks ──
from core.llm.advanced_model_router import get_advanced_router
decision = await get_advanced_router().route_with_confidence(prompt_text, task_type)
if decision.is_deterministic and decision.deterministic_result:
    logger.info(f"[LLMGateway] Tier 0 fast-path: pattern={decision.matched_pattern} confidence={decision.confidence:.2f}")
    return {
        "success": True,
        "text": json.dumps(decision.deterministic_result, indent=2),
        "model": "tier0-deterministic",
        "cost": 0.0,
        "cached": False,
        "tier0_bypass": True,
    }
```

Add a lazy accessor at module level (to avoid circular import with `advanced_model_router.py`):

```python
# At module-level in advanced_model_router.py (after AdvancedModelRouter class):
_router_instance: AdvancedModelRouter | None = None
def get_advanced_router() -> AdvancedModelRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = AdvancedModelRouter()
    return _router_instance
```

### Task 3: JSON Schema Validation for SkillManager

**Pre-Flight Check (5Q):**
1. ✅ Already done? — `BaseSkill` (base.py:1) has no schema; `SkillManager` has AST sandbox but no input validation.
2. Files: `core/skills/base.py`, `core/skill_manager.py`
3. Verify: `tests/test_skill_structured.py`
4. Side effects: `synthesize_skill_schema()` output already includes `"parameters"` list — we validate against it
5. Single commit: yes

**Changes to `core/skills/base.py`:**

```python
from typing import Any

class BaseSkill:
    """Base class for all skills."""

    # Schema definition — subclasses override this
    parameters: list[dict[str, str]] = []

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def get_schema(self) -> list[dict[str, str]]:
        """Return the expected parameters schema for this skill."""
        return self.parameters

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate and sanitize arguments against the skill's schema.
        Raises ValueError on missing required or type mismatch."""
        schema = self.get_schema()
        validated = {}

        for param in schema:
            pname = param["name"]
            ptype = param.get("type", "string")
            if pname not in args:
                # Check if required — if no "default" key, it's required
                if "default" not in param:
                    raise ValueError(f"Missing required parameter: {pname}")
                validated[pname] = param["default"]
            else:
                raw = args[pname]
                # Type coercion with safety
                if ptype == "string":
                    validated[pname] = str(raw)
                elif ptype == "integer":
                    validated[pname] = int(raw)
                elif ptype == "number":
                    validated[pname] = float(raw)
                elif ptype == "boolean":
                    validated[pname] = bool(raw)
                else:
                    validated[pname] = raw  # fallback: accept as-is

        return validated

    def run(self, *args, **kwargs):
        raise NotImplementedError
```

**Changes to `core/skill_manager.py`:**

Add `validate_and_sanitize_tool_input()` method to `SkillManager`:

```python
async def validate_and_sanitize_tool_input(self, skill_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate tool arguments against the skill's registered schema before execution.
    
    This enforces strict schema compliance for all agent skills (SyncGuard, MarketplaceAgent,
    CheckpointManager), preventing hallucinated or malformed tool inputs from causing
    downstream failures.
    """
    skill = await self.get_skill(skill_name)
    if hasattr(skill, "validate_args"):
        return skill.validate_args(args)
    # Fallback for skills without explicit schema
    logger.warning(f"Skill '{skill_name}' has no parameter schema — skipping validation")
    return args
```

### Task 4: Multi-Needle Context Retrieval

**Pre-Flight Check (5Q):**
1. ✅ Already done? — `query_context()` (memory_service.py:320) does single-vector cosine similarity. No multi-hop cross-referencing.
2. Files: `services/memory_service.py`, `core/unified_memory.py`, `api/routes/unified_memory_api.py`
3. Verify: `tests/test_multi_needle.py` — store 5 memory entries, query with cross-reference prompt, verify non-relevant snippets are filtered
4. Side effects: None — additive method only
5. Single commit: yes

**Changes to `services/memory_service.py`:**

Add `query_multi_needle_context()` method to `CascadeMemoryService`:

```python
def query_multi_needle_context(
    self,
    query: str,
    top_k: int = 5,
    session_id: str | None = None,
    needles_count: int = 3,
) -> list[dict[str, Any]]:
    """Multi-hop cross-referencing: retrieve top_k, then score subsets for coherence.

    Instead of returning isolated similarity-ranked results, this method:
    1. Retrieves top_k candidates (standard vector similarity)
    2. Selects the top `needles_count` most relevant by primary score
    3. Computes cross-similarity between needle pairs — filters out
       candidates that are unrelated (low cross-similarity with the
       primary needle cluster)
    """
    # Step 1: Get raw results
    raw_results = self.query_context(prompt=query, top_k=top_k, session_id=session_id)
    if len(raw_results) <= 1:
        return raw_results

    # Step 2: Extract top needles
    needles = raw_results[:needles_count]
    candidates = raw_results[needles_count:]

    if not candidates:
        return raw_results

    # Step 3: Cross-reference scoring
    # Compute the centroid of primary needle embeddings
    needle_vectors = []
    for needle in needles:
        if "embedding" in needle and needle["embedding"]:
            try:
                vec = json.loads(needle["embedding"]) if isinstance(needle["embedding"], str) else needle["embedding"]
                needle_vectors.append(vec)
            except (json.JSONDecodeError, TypeError):
                continue

    if not needle_vectors:
        return raw_results  # Fallback: return raw results if we can't parse embeddings

    # Centroid of primary needles
    centroid = [0.0] * len(needle_vectors[0])
    for vec in needle_vectors:
        for i, v in enumerate(vec):
            centroid[i] += v
    centroid = [c / len(needle_vectors) for c in centroid]

    # Step 4: Score candidates by cross-similarity to the centroid
    # Only keep candidates that are semantically coherent with the needle cluster
    filtered = []
    needle_score = self._cosine_similarity(self._embed(query), centroid)

    for candidate in candidates:
        if "embedding" in candidate and candidate["embedding"]:
            try:
                cand_vec = json.loads(candidate["embedding"]) if isinstance(candidate["embedding"], str) else candidate["embedding"]
                cross_score = self._cosine_similarity(cand_vec, centroid)
                # Cross-similarity must be at least 50% of query-to-centroid similarity
                if cross_score >= needle_score * 0.5:
                    filtered.append(candidate)
            except (json.JSONDecodeError, TypeError):
                filtered.append(candidate)  # Keep if we can't score
        else:
            filtered.append(candidate)

    # Merge needles + filtered candidates, re-sort by score
    combined = needles + filtered
    combined.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return combined[:top_k]
```

**Changes to `core/unified_memory.py`:**

Add `query_multi_needle_context()` to `UnifiedMemoryInterface`:

```python
def query_multi_needle_context(
    self,
    query: str,
    top_k: int = 5,
    session_id: str | None = None,
    needles_count: int = 3,
) -> list[dict[str, Any]]:
    """Multi-hop cross-reference context retrieval across long-term memory.

    Filters out irrelevant 'haystack' noise by evaluating semantic coherence
    across multiple retrieved memory snippets."""
    try:
        return self.long_term_memory.query_multi_needle_context(
            query=query,
            top_k=top_k,
            session_id=session_id,
            needles_count=needles_count,
        )
    except Exception as e:
        logger.error(f"Failed to query multi-needle context: {e}")
        return []
```

**Changes to `api/routes/unified_memory_api.py`:**

Add new endpoint:

```python
from pydantic import BaseModel

class MultiNeedleQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    session_id: str | None = None
    needles_count: int = 3

@router.post("/long-term/multi-needle-query")
async def multi_needle_query_endpoint(req: MultiNeedleQueryRequest):
    """Multi-hop cross-referenced context retrieval from long-term memory."""
    results = unified_memory.query_multi_needle_context(
        query=req.query,
        top_k=req.top_k,
        session_id=req.session_id,
        needles_count=req.needles_count,
    )
    return {"results": results, "count": len(results)}
```

---

## Dependency Graph & Integration Points

```
AdvancedModelRouter (Task 1)
  ├── imported by LLMGateway.acompletion() (Task 2)
  └── get_advanced_router() singleton avoids circular import

SkillManager (Task 3)
  ├── depends on BaseSkill.validate_args() (Task 3)
  └── used by SyncGuard, MarketplaceAgent, CheckpointManager (no changes needed)

CascadeMemoryService (Task 4)
  ├── extends existing query_context() (no break)
  └── UnifiedMemoryInterface (Task 4) → API endpoint (Task 4)
```

No changes needed to:
- `services/llm/llm_router.py` — stays as Tier 1/2 provider orchestrator
- `core/llm/provider_router.py` — latency-weighted routing stays
- `core/performance_enhancer.py` — model selection stays

---

## Verification Plan

### Automated Tests (all use existing pytest + pytest-anyio conventions)

```bash
# Task 1 & 2: Confidence gate + LLM gateway bypass
cd "F:\supremeai backup\backend"
poetry run pytest tests/test_confidence_gate.py -v

# Task 3: Skill schema validation
poetry run pytest tests/test_skill_structured.py -v

# Task 4: Multi-needle memory
poetry run pytest tests/test_multi_needle.py -v

# Regression: existing gateway + router tests must still pass
poetry run pytest tests/test_provider_failover_chain.py tests/test_skill_manager.py -v
```

**Test 1: `tests/test_confidence_gate.py`**
- `test_deterministic_task_bypasses_llm` — mock `litellm.acompletion`, assert it's never called for pattern-matched prompts
- `test_high_confidence_route_selection` — verify `route_with_confidence()` returns correct `ConfidenceDecision`
- `test_complex_prompt_does_not_bypass` — `"Analyze complex distributed race condition"` should have `is_deterministic=False`

**Test 2: `tests/test_skill_structured.py`**
- `test_valid_args_pass_validation` — correct args pass through
- `test_missing_required_arg_raises` — missing required param raises `ValueError`
- `test_type_coercion` — string "42" coerced to int 42

**Test 3: `tests/test_multi_needle.py`**
- Uses temporary SQLite DB (per `memory_service.py` `__main__` pattern)
- Stores 5 memory entries with different embeddings
- Queries with cross-reference prompt
- Verifies irrelevant snippets are filtered vs. raw `query_context()` results

### Manual Hard Test (per AGENTS.md §4 Real Testing Protocol)

```bash
# Start backend locally
cd "F:\supremeai backup\backend"
python -m uvicorn core.app:app --reload --port 8080

# Tier 0 test (should NOT make any LLM API call):
curl -X POST http://localhost:8080/api/v1/llm/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Search PyPI for pandas", "task_type": "general"}'
# Expected: {"tier0_bypass": true, "cost": 0.0, "model": "tier0-deterministic"}

# Multi-needle memory test:
curl -X POST http://localhost:8080/api/v1/unified-memory/long-term/multi-needle-query \
  -H "Content-Type: application/json" \
  -d '{"query": "Supabase pgvector connection pooling", "top_k": 5, "needles_count": 2}'
# Expected: filtered results only, fewer tokens sent to downstream LLM
```

### Quality Gates

```bash
# Lint (project uses ruff at root)
cd "F:\supremeai backup" && ruff check backend/core/llm/advanced_model_router.py backend/core/skill_manager.py backend/services/memory_service.py

# Type check
cd "F:\supremeai backup\backend" && poetry run mypy core/llm/advanced_model_router.py --ignore-missing-imports

# Syntax check all modified modules
python -c "import ast; [ast.parse(open(f).read()) for f in ['core/llm/advanced_model_router.py', 'core/llm/llm_gateway.py', 'core/skill_manager.py', 'core/skills/base.py', 'services/memory_service.py', 'core/unified_memory.py', 'api/routes/unified_memory_api.py']]; print('All modules parse OK')"
```

---

## Rollout Order (Atomic Commits)

| Order | Commit | Scope | Risk |
|-------|--------|-------|------|
| 1 | `feat: add Tier0 deterministic dispatcher to AdvancedModelRouter` | `core/llm/advanced_model_router.py` + test | Low — additive class, no caller changes |
| 2 | `feat: integrate fast-path bypass into LLMGateway.acompletion` | `core/llm/llm_gateway.py` | Low — only triggers on matched patterns |
| 3 | `feat: add JSON schema validation to BaseSkill + SkillManager` | `core/skills/base.py`, `core/skill_manager.py` | Low — validation only blocks bad inputs |
| 4 | `feat: add multi-needle cross-reference query to memory service` | `services/memory_service.py`, `core/unified_memory.py`, `api/routes/unified_memory_api.py` | Low — additive method, existing `query_context` untouched |
| 5 | `test: add confidence gate, skill validation, multi-needle tests` | `tests/test_confidence_gate.py`, `tests/test_skill_structured.py`, `tests/test_multi_needle.py` | — |

All changes are **additive or guarded** — no existing code path is broken. The `is_deterministic` flag defaults to `False` for any prompt that doesn't match a pattern, so existing behavior is 100% preserved.
