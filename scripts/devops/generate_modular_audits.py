# ruff: noqa: E501
"""
SupremeAI 2.0 — Elite Modular Audit Generator (v2.0)
======================================================
Generates 14 + 1 hyper-focused, self-contained audit markdown files into
`docs/autogen/modular_audits/` that ANY AI auditor (GPT-4o, Claude 3.5,
Gemini 1.5 Pro, etc.) can use to give their absolute BEST review.

Key upgrades over v1:
  - Removes the 15-file cap: all files embedded
  - AI-optimized audit prompt header per part
  - Per-file metadata: size, line count, last-modified
  - Token budget estimate so auditor knows what to expect
  - Smart skip: __pycache__, node_modules, .pyc, binary, autogen dirs
  - Generates a master INDEX.md for easy navigation
  - Output now goes to docs/autogen/modular_audits/

বাংলা মন্তব্য: এই স্ক্রিপ্টটি যেকোনো AI কে সর্বোচ্চ মানের অডিট দেওয়ার জন্য
একটি সম্পূর্ণ, স্বনির্ভর (self-contained) কনটেক্সট প্যাকেজ তৈরি করে।
"""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: স্কিপ করা এক্সটেনশন — বাইনারি, ক্যাশ, বা অপ্রয়োজনীয় ফাইল
# ─────────────────────────────────────────────────────────────────────────────
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".pdf", ".docx", ".xlsx", ".zip", ".gz", ".tar", ".whl",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".wav", ".ogg", ".avi",
    ".lock",  # poetry.lock, package-lock.json — too large
    ".map",   # JS source maps
}

# বাংলা মন্তব্য: এই ডিরেক্টরিগুলো সম্পূর্ণ স্কিপ করা হবে
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv", ".env",
    "dist", "build", ".next", ".turbo", ".cache", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "autogen",  # skip own output dir
}

# বাংলা মন্তব্য: ফাইল এক্সটেনশন থেকে markdown code fence ভাষা নির্ধারণ
EXT_TO_LANG: dict[str, str] = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript",
    ".jsx": "jsx", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".md": "markdown", ".sh": "bash", ".bash": "bash",
    ".env": "bash", ".tf": "hcl", ".hcl": "hcl", ".sql": "sql",
    ".dart": "dart", ".go": "go", ".rs": "rust", ".html": "html",
    ".css": "css", ".scss": "scss", ".xml": "xml", ".proto": "protobuf",
    ".graphql": "graphql", ".dockerfile": "dockerfile",
}

# Max file size to embed (skip files larger than this — e.g. large test fixtures)
MAX_FILE_BYTES = 150_000  # 150 KB

# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: ১৪টি মডিউলার অডিট পার্টের সংজ্ঞা
# ─────────────────────────────────────────────────────────────────────────────
AUDIT_PARTS: dict[str, dict] = {
    "PART_01_LLM_GATEWAY_ROUTER.md": {
        "title": "Part 1: LLM Gateway, Predictive Router & Quota Governor",
        "description": "Multi-provider AI routing, predictive free-tier quota governor, and gateway fallback logic.",
        "focus_areas": [
            "Provider selection & fallback chain correctness",
            "Quota enforcement & Redis-based token budget atomicity",
            "Circuit breaker open/close logic under concurrent load",
            "Rate limit tracking accuracy across providers",
        ],
        "target_paths": [
            "backend/core/llm_router.py",
            "backend/core/llm/free_tier_tracker.py",
            "backend/core/llm/distributed_budget.py",
            "backend/core/autonoguard_engine.py",
        ],
    },
    "PART_02_SECURITY_GUARDRAILS.md": {
        "title": "Part 2: Security Guardrails, Prompt Firewall & RBAC",
        "description": "Prompt firewall, anti-hacking middleware, rate limiters, honeypot, and RBAC authentication.",
        "focus_areas": [
            "Prompt injection & jailbreak detection coverage",
            "CORS origin validation bypass risks",
            "RBAC role escalation vectors",
            "Rate limiter bypass under distributed load",
            "Honeypot fingerprinting effectiveness",
        ],
        "target_paths": ["backend/core/security/"],
    },
    "PART_03_MULTI_DB_OUTBOX.md": {
        "title": "Part 3: Multi-DB Architecture & Transactional Outbox",
        "description": "Transactional outbox pattern, Supabase, Cloudflare D1, Upstash Redis, and code_to_db_sync daemon.",
        "focus_areas": [
            "Outbox event delivery guarantees (at-least-once vs exactly-once)",
            "Multi-DB router fail-closed correctness under all circuit breaker states",
            "Feature flag percentage rollout determinism",
            "Write-behind batcher flush atomicity",
        ],
        "target_paths": [
            "backend/database/multi_db_router.py",
            "backend/pipelines/code_to_db_sync.py",
            "backend/core/persistence/write_behind.py",
            "backend/database/supabase_client.py",
        ],
    },
    "PART_04_TIER8_SELF_EVOLUTION.md": {
        "title": "Part 4: Tier 8 Self-Evolution Engine & Auto-Healer",
        "description": "Error fingerprinting, mutation depth guardrails, model training, and auto-git-revert triggers.",
        "focus_areas": [
            "Mutation depth <= 3 guardrail enforcement",
            "Fingerprint collision risk in failure_fingerprint.py",
            "Rollback monitor gcloud dependency failure handling",
            "Model trainer status fabrication prevention",
        ],
        "target_paths": [
            "backend/core/auto_healer_service.py",
            "backend/core/failure_fingerprint.py",
            "backend/tools/learning/model_trainer.py",
            "backend/core/resilience/rollback_monitor.py",
        ],
    },
    "PART_05_SWARM_WEBSOCKETS.md": {
        "title": "Part 5: Swarm Real-Time WebSockets & Telemetry Buffer",
        "description": "250ms sliding window ring-buffer streaming, Redis pubsub, and HITL escalation channels.",
        "focus_areas": [
            "PubSub message delivery ordering & backpressure",
            "Oversized broadcast payload handling",
            "Wall-clock timer flush correctness in buffered_subscribe",
            "Admin route authentication coverage completeness",
        ],
        "target_paths": [
            "backend/core/swarm_pubsub.py",
            "backend/core/admin_routes.py",
        ],
    },
    "PART_06_P2P_COMPUTE_MESH.md": {
        "title": "Part 6: P2P Compute Mesh & Zero-Trust Sandboxing",
        "description": "Zero-trust MicroVM sandbox execution, hardware resource broker, and crypto proof-of-work credit system.",
        "focus_areas": [
            "Resource broker race conditions under concurrent allocation",
            "MicroVM escape vectors (filesystem, network, process)",
            "Credit deduction atomicity & refund guarantees",
            "Firecracker/gVisor payload injection security",
        ],
        "target_paths": [
            "backend/p2p/resource_broker.py",
            "backend/p2p/credit_system.py",
            "backend/core/microvm_sandbox.py",
        ],
    },
    "PART_07_BACKEND_API_ROUTERS.md": {
        "title": "Part 7: Backend API Routers, Middleware & Core App Builder",
        "description": "FastAPI application entrypoints, middleware stack, dependencies, and v1 API routers.",
        "focus_areas": [
            "Middleware ordering & dependency injection safety",
            "Unauthenticated endpoint exposure",
            "Request validation & schema enforcement gaps",
            "CORS, HTTPS, and security header configuration",
        ],
        "target_paths": [
            "backend/api/",
            "backend/core/app.py",
            "backend/core/app_builder.py",
        ],
    },
    "PART_08_BACKEND_AI_AGENT_TOOLS.md": {
        "title": "Part 8: Backend AI Agents, MCP Tools & Orchestration Services",
        "description": "Autonomous AI agent tools, MCP server integrations, checkpointing, and execution tools.",
        "focus_areas": [
            "Agent loop infinite recursion risks",
            "MCP tool permission scope creep",
            "Checkpoint state integrity under concurrent agents",
            "External tool execution sandboxing completeness",
        ],
        "target_paths": ["backend/tools/"],
    },
    "PART_09_REACT_STUDIO_CLIENT.md": {
        "title": "Part 9: React/Vite Studio Client Web Application",
        "description": "React Studio Client frontend app, Admin Console UI components, and state management hooks.",
        "focus_areas": [
            "XSS vectors in rendered user/AI content",
            "Auth token storage & expiry handling in zustand stores",
            "Error boundary completeness & telemetry reporting",
            "Sensitive data leakage in frontend error messages",
        ],
        "target_paths": ["apps/studio-client/src/"],
    },
    "PART_10_FLUTTER_MOBILE_APP.md": {
        "title": "Part 10: Flutter Mobile Cross-Platform Application",
        "description": "Flutter Mobile application source code, state management, and mobile API services.",
        "focus_areas": [
            "API key storage security (Keychain/Keystore vs plain storage)",
            "Certificate pinning implementation",
            "Deep link validation & open redirect risks",
            "Biometric auth bypass vectors",
        ],
        "target_paths": ["apps/mobile/"],
    },
    "PART_11_PACKAGES_SHARED_TYPES.md": {
        "title": "Part 11: Shared Monorepo Packages & TypeScript Interfaces",
        "description": "Monorepo shared TypeScript types, design tokens, and reusable UI components.",
        "focus_areas": [
            "Type safety gaps that could mask runtime errors",
            "Shared secret / credential handling in shared packages",
            "Circular dependency risks",
        ],
        "target_paths": ["packages/"],
    },
    "PART_12_TEST_SUITE_PYTEST.md": {
        "title": "Part 12: Pytest Test Suite & Integration Tests",
        "description": "Backend pytest test suite, API integration test cases, and resilience coverage.",
        "focus_areas": [
            "Test coverage gaps in security-critical paths",
            "Mocking correctness (wrong module paths, incomplete mocks)",
            "Async test isolation & event loop leaks",
            "Integration test environment variable dependency risks",
        ],
        "target_paths": ["backend/tests/"],
    },
    "PART_13_CICD_DEV_WORKFLOWS.md": {
        "title": "Part 13: GitHub Actions CI/CD & DevOps Scripts",
        "description": "Monorepo GitHub Actions workflows, maintenance automation pipelines, and CI scripts.",
        "focus_areas": [
            "Secret exposure in workflow logs (echo, env printing)",
            "Workflow trigger scope (pull_request vs push)",
            "Third-party action pinning (SHA vs tag)",
            "Script injection via untrusted PR data",
        ],
        "target_paths": [
            ".github/workflows/",
            "scripts/ci/",
            "scripts/devops/",
        ],
    },
    "PART_14_CLOUD_INFRASTRUCTURE.md": {
        "title": "Part 14: Cloud Infrastructure, Edge Workers & Docker Prod",
        "description": "Terraform, Cloudflare Worker JS, Firebase Functions, Docker Prod, and deployment specs.",
        "focus_areas": [
            "Docker image hardening (non-root user, read-only FS)",
            "Terraform state file secret exposure",
            "Cloudflare Worker secret binding completeness",
            "Network exposure of internal services",
        ],
        "target_paths": [
            "infrastructure/",
            "cloudflare-worker/",
            "Dockerfile",
            "render.yaml",
            "vercel.json",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: helper ফাংশন — ফাইল সংগ্রহ করে metadata সহ
# ─────────────────────────────────────────────────────────────────────────────

def _should_skip(path: Path) -> bool:
    """বাংলা মন্তব্য: ফাইলটি স্কিপ করা উচিত কিনা তা নির্ধারণ করে।"""
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    if path.name.startswith("."):
        return True
    if path.stat().st_size > MAX_FILE_BYTES:
        return False  # Still embed, but truncated
    return False


def _collect_files(root_path: Path, target: str) -> list[Path]:
    """বাংলা মন্তব্য: একটি target path থেকে সমস্ত eligible ফাইল সংগ্রহ করে।"""
    full_target = root_path / target
    if not full_target.exists():
        return []

    if full_target.is_file():
        return [full_target]

    # Directory — recursively collect, skip forbidden dirs
    collected: list[Path] = []
    for child in sorted(full_target.rglob("*")):
        if not child.is_file():
            continue
        # Check if any parent dir is in SKIP_DIRS
        if any(part in SKIP_DIRS for part in child.parts):
            continue
        if child.suffix.lower() in SKIP_EXTENSIONS:
            continue
        if child.name.startswith("."):
            continue
        collected.append(child)
    return collected


def _get_git_log(filepath: Path, root_path: Path) -> str:
    """বাংলা মন্তব্য: ফাইলের সর্বশেষ ৩টি git commit সংক্ষিপ্তভাবে দেখায়।"""
    try:
        rel = str(filepath.relative_to(root_path)).replace("\\", "/")
        result = subprocess.run(
            ["git", "log", "--oneline", "-3", "--", rel],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=root_path, timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        if lines:
            return "\n".join(f"  - `{ln}`" for ln in lines)
        return "  - *(no commits yet)*"
    except Exception:  # noqa: BLE001
        return "  - *(git log unavailable)*"


def _estimate_tokens(text: str) -> int:
    """বাংলা মন্তব্য: Rough token estimate (1 token ≈ 4 chars for English code)."""
    return max(1, len(text) // 4)


def _embed_file(filepath: Path, rel_path: str, root_path: Path) -> tuple[str, dict]:
    """বাংলা মন্তব্য: একটি ফাইলের সম্পূর্ণ content markdown codeblock-এ embed করে।"""
    ext = filepath.suffix.lower()
    lang = EXT_TO_LANG.get(ext, ext.lstrip(".") or "text")
    # Special case: Dockerfile
    if filepath.name.lower() == "dockerfile":
        lang = "dockerfile"

    size_bytes = filepath.stat().st_size
    try:
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        mtime = "unknown"

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        content = f"# Error reading file: {exc}"

    line_count = content.count("\n") + 1
    truncated = ""
    if size_bytes > MAX_FILE_BYTES:
        # Embed first 120 lines + last 20 lines with a note
        lines = content.splitlines()
        head = "\n".join(lines[:120])
        tail = "\n".join(lines[-20:])
        content = f"{head}\n\n# ... [{line_count - 140} lines truncated — file too large] ...\n\n{tail}"
        truncated = " ⚠️ *truncated*"

    git_log = _get_git_log(filepath, root_path)

    block = (
        f"### 📄 `{rel_path}`{truncated}\n\n"
        f"> **Size:** `{size_bytes:,} bytes` | "
        f"**Lines:** `{line_count:,}` | "
        f"**Modified:** `{mtime}`\n>\n"
        f"> **Recent commits:**\n{git_log}\n\n"
        f"```{lang}\n{content}\n```\n"
    )
    meta = {
        "path": rel_path,
        "size_bytes": size_bytes,
        "lines": line_count,
        "tokens": _estimate_tokens(content),
    }
    return block, meta


# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: AI-optimized audit prompt — যেকোনো AI সর্বোচ্চ মানের রিভিউ দিতে পারবে
# ─────────────────────────────────────────────────────────────────────────────

def _build_ai_audit_prompt(title: str, description: str, focus_areas: list[str]) -> str:
    areas_md = "\n".join(f"  - {a}" for a in focus_areas)
    return f"""## 🤖 AI Audit Instructions

> **You are acting as a Senior Security & Code Quality Auditor.**
> This document is **100% self-contained** — all source code is embedded below.
> You do NOT need access to any external repository or file system.

### Your Mission
Perform a **deep, exhaustive audit** of the **{title}** subsystem.
Your audit must be production-grade — do not give vague or generic feedback.

### Mandatory Focus Areas for This Module
{areas_md}

### Required Output Format
For every issue found, provide **exactly**:
1. **🔴 Severity:** `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `INFO`
2. **📁 File + Line:** e.g. `backend/core/llm_router.py:L142`
3. **🐛 Issue Title:** One-line summary
4. **📖 Description:** What is wrong and why it matters
5. **🛠️ Delta Patch:** Exact code fix (before/after diff)
6. **✅ Test Suggestion:** How to verify the fix

### Quality Gates (you must meet ALL of these)
- [ ] Zero hallucinations — only cite actual code lines visible in Section 3
- [ ] Every CRITICAL/HIGH issue must have a working patch
- [ ] Do not repeat pre-existing comments as issues
- [ ] Check for Bangla comments (`# বাংলা মন্তব্য`) — verify they match the code logic
- [ ] Flag any `# TODO`, `pass`, or `NotImplemented` left in production paths

---"""


# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: মূল generation ফাংশন
# ─────────────────────────────────────────────────────────────────────────────

def generate_audit_markdowns(project_root: str = ".") -> None:
    """
    বাংলা মন্তব্য: সম্পূর্ণ monorepo স্ক্যান করে ১৪টি AI-optimized audit ফাইল তৈরি করে।
    সব ফাইল docs/autogen/modular_audits/ ফোল্ডারে যাবে।
    """
    root_path = Path(project_root).resolve()
    output_dir = root_path / "docs" / "autogen" / "modular_audits"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*70}")
    print(f"  SupremeAI 2.0 — Elite Modular Audit Generator v2.0")
    print(f"  Output  : {output_dir}")
    print(f"  Started : {timestamp}")
    print(f"{'='*70}\n")

    index_rows: list[str] = []
    grand_total_files = 0
    grand_total_bytes = 0
    grand_total_tokens = 0

    for filename, meta in AUDIT_PARTS.items():
        filepath = output_dir / filename
        title = meta["title"]
        description = meta["description"]
        focus_areas = meta.get("focus_areas", [])

        print(f"  [>] Generating {filename} ...", end="", flush=True)

        # ── Collect all files ──────────────────────────────────────────────
        all_files: list[Path] = []
        missing_targets: list[str] = []

        for target in meta["target_paths"]:
            found = _collect_files(root_path, target)
            if found:
                all_files.extend(found)
            else:
                missing_targets.append(target)

        # De-duplicate (in case of overlapping target paths)
        seen: set[Path] = set()
        unique_files: list[Path] = []
        for f in all_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        # ── Build inventory + embedded blocks ─────────────────────────────
        inventory_lines: list[str] = []
        embedded_blocks: list[str] = []
        part_files = 0
        part_bytes = 0
        part_tokens = 0

        for child in unique_files:
            rel = str(child.relative_to(root_path)).replace("\\", "/")
            size = child.stat().st_size
            block, file_meta = _embed_file(child, rel, root_path)
            inventory_lines.append(
                f"| `{rel}` | {size:,} B | {file_meta['lines']:,} | ~{file_meta['tokens']:,} |"
            )
            embedded_blocks.append(block)
            part_files += 1
            part_bytes += size
            part_tokens += file_meta["tokens"]

        for m in missing_targets:
            inventory_lines.append(f"| `{m}` | — | — | *(not found)* |")

        grand_total_files += part_files
        grand_total_bytes += part_bytes
        grand_total_tokens += part_tokens

        inventory_md = "\n".join(inventory_lines) if inventory_lines else "*(no files found)*"
        source_dump = "\n---\n".join(embedded_blocks) if embedded_blocks else "*(no source files)*"
        ai_prompt = _build_ai_audit_prompt(title, description, focus_areas)

        # ── Write part file ────────────────────────────────────────────────
        content = f"""# {title}

> **Audit Generated:** `{timestamp}`
> **Description:** {description}
> **Files:** `{part_files}` | **Total Size:** `{part_bytes:,} bytes` | **Est. Tokens:** `~{part_tokens:,}`
> **Status:** `SELF_CONTAINED — READY FOR AI AUDIT`

---

{ai_prompt}

---

## 2. 📁 File Inventory

| File Path | Size | Lines | Est. Tokens |
|-----------|------|-------|-------------|
{inventory_md}

**Totals:** `{part_files}` files · `{part_bytes:,}` bytes · `~{part_tokens:,}` tokens

---

## 3. 📦 Complete Source Code

> **Instructions for AI:** Read ALL code below before writing any findings.
> Line numbers in your output must match the actual code shown here.

{source_dump}

---

## 4. 🔴 Identified Vulnerabilities & Issues

*Populate this section by feeding Section 2 + Section 3 into your AI auditor.*

<!-- AUDIT_START -->
<!-- AUDIT_END -->

---

## 5. 🛠️ Recommended Delta Patches

*Each patch must be in unified diff format with file path and line numbers.*

---

## 6. ✅ Verification Checklist

- [ ] All CRITICAL/HIGH patches applied and tested
- [ ] Regression tests pass for changed files
- [ ] Bangla comments updated to reflect changes
- [ ] No new `# TODO` or `pass` introduced in production paths

---
*Generated by SupremeAI 2.0 Elite Audit Generator v2.0*
"""
        filepath.write_text(content, encoding="utf-8")
        size_kb = len(content) / 1024
        print(f" [OK] ({part_files} files, {size_kb:.0f} KB, ~{part_tokens:,} tokens)")

        # Index entry
        index_rows.append(
            f"| [{filename}](./{filename}) | {part_files} | {part_bytes:,} B | ~{part_tokens:,} |"
        )

    # ── Generate master INDEX.md ───────────────────────────────────────────
    index_path = output_dir / "INDEX.md"
    index_table = "\n".join(index_rows)
    index_content = f"""# SupremeAI 2.0 — Modular Audit Index

> **Generated:** `{timestamp}`
> **Total Files Covered:** `{grand_total_files}`
> **Total Codebase Size:** `{grand_total_bytes:,} bytes`
> **Total Estimated Tokens:** `~{grand_total_tokens:,}`

---

## How to Use These Audits

1. **Pick a Part** from the table below based on what you want audited.
2. **Open the Part file** — it contains everything (instructions, code, checklist).
3. **Paste the full Part file** into your AI assistant (GPT-4o / Claude / Gemini).
4. **The AI will self-audit** using the embedded instructions and source code.
5. **Paste the AI's output** back into Section 4 (Vulnerabilities) of the Part file.

> **Tip:** For maximum audit quality, use a model with **128K+ context window**
> and instruct it to read ALL of Section 3 before answering.

---

## Part Index

| Part File | Files | Size | Est. Tokens |
|-----------|-------|------|-------------|
{index_table}

---

## Audit Coverage Map

```
SupremeAI 2.0 Monorepo
├── backend/
│   ├── core/llm*           → PART_01 (LLM Gateway)
│   ├── core/security/      → PART_02 (Security Guardrails)
│   ├── database/           → PART_03 (Multi-DB Outbox)
│   ├── core/auto_healer*   → PART_04 (Self-Evolution)
│   ├── core/swarm_*        → PART_05 (WebSockets)
│   ├── core/admin_routes*  → PART_05 (Admin Auth)
│   ├── p2p/                → PART_06 (P2P Compute)
│   ├── core/microvm*       → PART_06 (Sandboxing)
│   ├── api/                → PART_07 (API Routers)
│   └── tools/              → PART_08 (AI Agent Tools)
├── apps/studio-client/     → PART_09 (React Frontend)
├── apps/mobile/            → PART_10 (Flutter Mobile)
├── packages/               → PART_11 (Shared Types)
├── backend/tests/          → PART_12 (Test Suite)
├── .github/workflows/      → PART_13 (CI/CD)
├── scripts/                → PART_13 (DevOps Scripts)
└── infrastructure/         → PART_14 (Cloud Infra)
```

---
*SupremeAI 2.0 Elite Audit Generator v2.0*
"""
    index_path.write_text(index_content, encoding="utf-8")

    print(f"\n{'='*70}")
    print(f"  [OK] INDEX.md generated: {index_path}")
    print(f"  [+]  Grand Total: {grand_total_files} files · "
          f"{grand_total_bytes:,} bytes · ~{grand_total_tokens:,} tokens")
    print(f"  [/]  Output: {output_dir}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    generate_audit_markdowns()
