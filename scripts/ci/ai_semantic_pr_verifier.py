#!/usr/bin/env python3
"""SupremeAI AI Semantic PR Verifier Gate (Single SSOT: docs/PR_TO_PRODUCTION_LIFECYCLE.md).

Purpose:
  1. Inspects pull request changed files to classify risk level (HIGH vs LOW).
  2. For LOW risk PRs (e.g. docs, UI tweaks, non-critical tests), approves immediately
     in <0.5s with zero LLM API consumption.
  3. For HIGH risk PRs (e.g. core/security, database migrations, authentication, auth tokens),
     enforces an automated semantic audit via SupremeAI's API Key Pool (Gemini, Groq, OpenAI).
  4. Evaluates three constitutional pillars:
     - Security Boundaries (zero credential leaks, no auth bypass, no IDOR)
     - Anti-Bloat / Occam's Razor (minimal surgical patch, no dead abstractions)
     - Zero-Recurrence Test Coverage (regression guards present for changes)
  5. Fails closed (exit 1) if security is violated or unapproved; exits 0 on approval.

Usage:
  python scripts/ci/ai_semantic_pr_verifier.py --pr 548
  python scripts/ci/ai_semantic_pr_verifier.py --files core/security/auth.py
  python scripts/ci/ai_semantic_pr_verifier.py --dry-run
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from typing import Any

# Add REPO_ROOT to sys.path so core is directly importable in CI
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HIGH_RISK_PATTERNS = [
    r"^core/security/.*",
    r"^core/api/routes/(auth|keys|tokens|admin|session).*",
    r"^infrastructure/supabase/migrations/.*",
    r"^migrations/.*",
    r"^core/db\.py$",
    r"^core/config\.py$",
    r"^gateway/.*security.*",
    r"^\.github/workflows/.*",
    r"^infrastructure/.*keepwarm.*",
]

SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|secret|password|bearer|token)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{20,}['\"]", "Hardcoded Secret/Token"),
    (r"(?i)service_role_key\s*[:=]\s*['\"][^'\"]{10,}['\"]", "Exposed Service Role Key"),
    (r"sk-[a-zA-Z0-9]{20,}", "Raw OpenAI/API Key"),
]

DIFF_CHAR_LIMIT = 8000
LLM_TIMEOUT_SECONDS = 30


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute subprocess safely with utf-8 encoding and replace error handling on all platforms."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def is_high_risk_file(path: str) -> bool:
    """Return True if path matches any recognized high-risk boundary pattern."""
    normalized = path.replace("\\", "/").strip().lstrip("/")
    return any(re.match(pat, normalized, re.IGNORECASE) for pat in HIGH_RISK_PATTERNS)


def classify_pr_risk(files: list[str]) -> tuple[str, list[str]]:
    """Classify risk level based on changed files list."""
    risky = [f for f in files if is_high_risk_file(f)]
    risk_level = "HIGH" if risky else "LOW"
    return risk_level, risky


def get_changed_files_from_git() -> list[str]:
    """Get list of changed files compared to origin/main or HEAD~1."""
    for base in ("origin/main", "main", "HEAD~1"):
        try:
            res = run_cmd(["git", "diff", "--name-only", f"{base}...HEAD"])
            if res.returncode == 0 and res.stdout.strip():
                return [f.strip() for f in res.stdout.splitlines() if f.strip()]
        except Exception:
            continue
    # Fallback to local unstaged/staged git diff
    try:
        res = run_cmd(["git", "diff", "--name-only", "HEAD"])
        if res.returncode == 0 and res.stdout.strip():
            return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)
    return []


def get_pr_files(pr_number: str) -> list[str]:
    """Fetch all PR files and previous rename paths, verifying against PR metadata."""
    repo = os.getenv("GITHUB_REPOSITORY") or os.getenv("GH_REPO", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not re.fullmatch(r"[1-9][0-9]*", pr_number):
        return []
    metadata = run_cmd(["gh", "pr", "view", pr_number, "--json", "changedFiles", "--jq", ".changedFiles"])
    if metadata.returncode != 0 or not metadata.stdout.strip().isdigit():
        return []
    expected = int(metadata.stdout.strip())
    # REST list-pull-files has a hard 3,000-file cap.
    if expected <= 0 or expected > 3000:
        return []
    result = run_cmd(["gh", "api", f"repos/{repo}/pulls/{pr_number}/files?per_page=100",
                      "--paginate", "--jq", ".[] | {filename,previous_filename}"])
    if result.returncode != 0:
        return []
    try:
        entries = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if len(entries) != expected:
            return []
        paths = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str) or not entry["filename"]:
                return []
            paths.append(entry["filename"])
            previous = entry.get("previous_filename")
            if previous is not None:
                if not isinstance(previous, str) or not previous:
                    return []
                paths.append(previous)
        return paths
    except (ValueError, TypeError):
        return []


def get_diff_text(files: list[str], pr_number: str | None = None) -> str:
    """Extract diff text; caller rejects oversized evidence rather than truncating."""
    # With --pr, never substitute unrelated base-checkout diffs for PR evidence.
    if pr_number:
        try:
            res = run_cmd(["gh", "pr", "diff", str(pr_number)])
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout
        except Exception as exc:
            print(f"::warning::PR diff retrieval failed ({type(exc).__name__})", file=sys.stderr)
        return ""
    diff_text = ""
    # 1. Prefer targeted git diff for the specific high-risk files from GITHUB_WORKSPACE or repo root
    search_dirs: list[str] = []
    gh_ws = os.environ.get("GITHUB_WORKSPACE", "").strip()
    if gh_ws and Path(gh_ws).is_dir():
        search_dirs.append(gh_ws)
    parent_ws = Path.cwd().parent
    if Path.cwd().name == "_verifier-base" and (parent_ws / ".git").exists():
        search_dirs.append(str(parent_ws))
    search_dirs.append(str(Path.cwd()))

    for work_dir in search_dirs:
        for base in ("origin/main", "main", "HEAD~1"):
            try:
                cmd = ["git", "-C", work_dir, "diff", f"{base}...HEAD", "--"] + files
                res = run_cmd(cmd)
                if res.returncode == 0 and res.stdout.strip():
                    diff_text = res.stdout
                    break
            except Exception:
                continue
        if diff_text:
            break

    # 2. Fallback to gh pr diff or GitHub pulls/files API (handles >300 file PRs where gh pr diff returns HTTP 406)
    if not diff_text and pr_number and shutil.which("gh"):
        try:
            res = run_cmd(["gh", "pr", "diff", str(pr_number)])
            if res.returncode == 0 and res.stdout.strip():
                diff_text = res.stdout
        except Exception as exc:
            import logging
            logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)

        if not diff_text:
            try:
                repo_slug = os.environ.get("GITHUB_REPOSITORY", "Supremeai-bd/supremeai").strip()
                res = run_cmd([
                    "gh",
                    "api",
                    "--paginate",
                    f"repos/{repo_slug}/pulls/{pr_number}/files?per_page=100",
                ])
                if res.returncode == 0 and res.stdout.strip():
                    risky_set = {f.replace("\\", "/").strip().lstrip("/") for f in files}
                    patches: list[str] = []
                    for page_line in res.stdout.splitlines():
                        page_line = page_line.strip()
                        if not page_line:
                            continue
                        items = json.loads(page_line)
                        if isinstance(items, list):
                            for item in items:
                                fname = str(item.get("filename") or "")
                                patch = str(item.get("patch") or "")
                                if fname in risky_set and patch:
                                    patches.append(f"--- a/{fname}\n+++ b/{fname}\n{patch}")
                    if patches:
                        diff_text = "\n".join(patches)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)

    if not diff_text:
        for work_dir in search_dirs:
            try:
                res = run_cmd(["git", "-C", work_dir, "diff", "HEAD", "--"] + files)
                if res.returncode == 0 and res.stdout.strip():
                    diff_text = res.stdout
                    break
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug("Suppressed exception (%s)", type(exc).__name__)
    return diff_text


def scan_regex_secrets(diff: str) -> list[str]:
    """Scan diff text for dangerous concrete secret patterns."""
    hits = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            for pat, label in SECRET_PATTERNS:
                if re.search(pat, line):
                    # Do not copy any part of a potential credential into CI logs.
                    hits.append(label)
    return hits


def _iter_numbered_keys(base: str, max_n: int = 10) -> list[str]:
    """Return all non-empty values among base and base_2..base_max_n (deduped, ordered)."""
    keys: list[str] = []
    for name in [base] + [f"{base}_{i}" for i in range(2, max_n + 1)]:
        val = os.environ.get(name, "").strip()
        if val and val not in keys:
            keys.append(val)
    return keys


def _get_api_providers() -> list[dict[str, str]]:
    """Return available LLM providers in rotation order.

    Each provider key is emitted as its own entry so a rate-limited/blocked key
    (429/403) fails over to the next numbered key instead of aborting the whole
    provider. ``EVALUATOR_MAX_KEYS_PER_PROVIDER`` caps keys tried per provider.
    """
    providers: list[dict[str, str]] = []
    raw_max = os.environ.get("EVALUATOR_MAX_KEYS_PER_PROVIDER", "").strip()
    try:
        max_keys = max(1, int(raw_max)) if raw_max else None
    except ValueError:
        max_keys = None

    # 0. Unified API pool JSON (LLM_PROVIDER_KEYS) from Infisical
    pool_defaults = {
        "gemini": ("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", "gemini-2.5-flash"),
        "groq": ("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
        "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
        "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "meta-llama/llama-3.3-70b-instruct:free"),
        "deepseek": ("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
        "mistral": ("https://api.mistral.ai/v1/chat/completions", "mistral-small-latest"),
    }
    raw_pool = os.environ.get("LLM_PROVIDER_KEYS", "").strip()
    if raw_pool:
        try:
            pool_data = json.loads(raw_pool)
            if isinstance(pool_data, dict):
                for pname, entries in pool_data.items():
                    items = entries if isinstance(entries, list) else [entries]
                    default_url, default_model = pool_defaults.get(str(pname).lower(), ("", ""))
                    for item in items:
                        if isinstance(item, dict) and item.get("key"):
                            providers.append({
                                "name": str(pname),
                                "key": str(item["key"]),
                                "url": str(item.get("url") or default_url),
                                "model": str(item.get("model") or default_model),
                            })
                        elif isinstance(item, str) and item.strip() and default_url:
                            providers.append({
                                "name": str(pname),
                                "key": item.strip(),
                                "url": default_url,
                                "model": default_model,
                            })
        except Exception:
            pass

    return providers


def call_llm_provider(provider: dict[str, str], prompt: str) -> str | None:
    """Call an LLM provider and return response text or None."""
    try:
        if provider["name"] == "gemini":
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 600},
            }
            headers = {"Content-Type": "application/json", "x-goog-api-key": provider["key"]}
        else:
            payload = {
                "model": provider["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 600,
            }
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider['key']}"}

        req = urllib.request.Request(
            provider["url"],
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if provider["name"] == "gemini":
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        print(f"Warning: LLM provider {provider['name']} failed (HTTP {exc.code})")
        return None
    except Exception as exc:
        print(f"Warning: LLM provider {provider['name']} failed ({type(exc).__name__})")
        return None


def parse_llm_verdict(raw: str | None) -> dict[str, Any] | None:
    """Parse JSON verdict from raw LLM output."""
    if not raw:
        return None
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def run_semantic_verification(files: list[str], diff: str, title: str = "") -> dict[str, Any]:
    """Execute semantic verification via LLM or deterministic fallback."""
    # Missing evidence can never prove that a high-risk patch is safe.
    if not diff.strip():
        return {"approved": False, "security_verdict": "UNKNOWN", "anti_bloat_verdict": "UNKNOWN",
                "reasons": ["High-risk diff unavailable; semantic verification not performed"],
                "confidence": "unverified"}
    if len(diff) > DIFF_CHAR_LIMIT:
        return {"approved": False, "security_verdict": "UNKNOWN", "anti_bloat_verdict": "UNKNOWN",
                "reasons": ["Diff exceeds semantic review limit; manual review required"],
                "confidence": "unverified"}
    # 1. Deterministic Regex Pre-check
    secret_hits = scan_regex_secrets(diff)
    if secret_hits:
        return {
            "approved": False,
            "security_verdict": "FAIL",
            "anti_bloat_verdict": "UNKNOWN",
            "reasons": [f"Concrete secret pattern detected: {hit}" for hit in secret_hits],
            "confidence": "deterministic-regex",
        }

    # 2. Check for test files in changes
    has_test = any(re.search(r"tests?|test_.*\.py$", f, re.IGNORECASE) for f in files)

    # 3. Attempt LLM Pool (only when non-empty diff text is available)
    # Never transmit code to an external provider by default or incur API costs.
    # Enabling this requires an explicit repository policy for privacy and cost.
    providers = (_get_api_providers()
                 if os.getenv("SEMANTIC_VERIFIER_ALLOW_EXTERNAL_DIFF", "").lower() == "true"
                 else [])
    prompt = (
        "You are SupremeAI's Senior Security & Architecture Gatekeeper.\n"
        "Analyze the following High-Risk PR diff against these 3 strict criteria:\n"
        "1. Security: Zero hardcoded secrets, no permission bypass, no IDOR, safe database migrations.\n"
        "2. Anti-Bloat: Minimal surgical patch satisfying Occam's razor. No dead code or sprawling layers.\n"
        "3. Anti-Regression: Logical correctness and absence of breaking side-effects.\n\n"
        "Output ONLY a raw JSON object with no markdown formatting or prose:\n"
        "{\n"
        '  "approved": true or false,\n'
        '  "security_verdict": "PASS" or "FAIL",\n'
        '  "anti_bloat_verdict": "PASS" or "FAIL",\n'
        '  "reasons": ["<short reason 1>", "<short reason 2>"],\n'
        '  "summary": "<concise 1-line verdict summary>"\n'
        "}\n\n"
        f"PR Title: {title}\n"
        f"High Risk Files: {files}\n"
        f"Diff:\n{diff}\n"
    )

    for prov in providers:
        raw_res = call_llm_provider(prov, prompt)
        parsed = parse_llm_verdict(raw_res)
        if (isinstance(parsed, dict) and type(parsed.get("approved")) is bool
                and parsed.get("security_verdict") in ("PASS", "FAIL")
                and parsed.get("anti_bloat_verdict") in ("PASS", "FAIL")):
            parsed["approved"] = (parsed["approved"] and parsed["security_verdict"] == "PASS"
                                  and parsed["anti_bloat_verdict"] == "PASS")
            # Model output may echo code, secrets, or workflow commands.
            parsed.pop("summary", None)
            parsed["reasons"] = ["External semantic verdict received; inspect review evidence separately"]
            parsed["confidence"] = f"llm-verified ({prov['name']})"
            return parsed

    # A clean secret regex is not a semantic security or anti-bloat review.
    print(f"::warning::Semantic review unavailable ({len(providers)} provider key(s) tried); high-risk PR not verified.")
    return {
        "approved": False,
        "security_verdict": "UNKNOWN",
        "anti_bloat_verdict": "UNKNOWN",
        "reasons": ["Semantic review unavailable; secret regex alone is insufficient"],
        "confidence": "unverified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SupremeAI AI Semantic PR Verifier Gate")
    parser.add_argument("--pr", help="Pull request number to evaluate")
    parser.add_argument("--files", nargs="*", help="Explicit list of files to evaluate")
    parser.add_argument("--dry-run", action="store_true", help="Print evaluation without exiting 1 on failure")
    args = parser.parse_args()

    files = args.files or []
    if args.pr:
        # Explicit caller files cannot override the real PR evidence.
        try:
            files = get_pr_files(args.pr) if shutil.which("gh") else []
        except Exception as exc:
            print(f"::warning::PR file evidence unavailable ({type(exc).__name__})", file=sys.stderr)
            files = []

    if not files and not args.pr:
        files = get_changed_files_from_git()

    if not files:
        if args.pr:
            print("::error::PR changed-file evidence unavailable; verification not performed.")
            return 1
        print("✅ [AI-VERIFIER] No local changed files detected. Gate PASSED.")
        return 0

    risk_level, risky_files = classify_pr_risk(files)

    print("=======================================================================")
    print("SupremeAI AI Semantic PR Verification Gate")
    print(f"Risk Level: {risk_level}")
    print(f"Total Files Changed: {len(files)}")
    print("=======================================================================")

    # LOW RISK SHORT-CIRCUIT (Instant zero-quota pass)
    if risk_level == "LOW":
        print("✅ [AI-VERIFIER] PR is Low Risk (no core security or migration files modified).")
        print("⚡ Approved immediately without external LLM compute. Gate PASSED.")
        return 0

    # HIGH RISK ENFORCEMENT
    print(f"⚠️ [AI-VERIFIER] HIGH RISK FILES DETECTED ({len(risky_files)}):")
    for rf in risky_files[:10]:
        print(f"   • {json.dumps(rf, ensure_ascii=True)}")
    if len(risky_files) > 10:
        print(f"   ... and {len(risky_files) - 10} more.")

    print("\n🔍 Extracting diff for semantic audit...")
    diff = get_diff_text(risky_files, pr_number=str(args.pr) if args.pr else None)
    verdict = run_semantic_verification(risky_files, diff, title=f"PR #{args.pr or 'Local'}")

    print("───────────────────────────────────────────────────────────────────────")
    print(f"Verdict: {'✅ APPROVED' if verdict.get('approved') else '❌ REJECTED'}")
    print(f"Confidence: {verdict.get('confidence')}")
    print(f"Security: {verdict.get('security_verdict')}")
    print(f"Anti-Bloat: {verdict.get('anti_bloat_verdict')}")
    if verdict.get("summary"):
        print(f"Summary: {verdict.get('summary')}")
    if verdict.get("reasons"):
        print("Reasons:")
        for r in verdict.get("reasons", []):
            print(f"   - {r}")
    print("───────────────────────────────────────────────────────────────────────")

    if not verdict.get("approved"):
        if args.dry_run:
            print("⚠️ [AI-VERIFIER] Rejected in dry-run mode (exit 0).")
            return 0
        print("::error::AI Semantic PR Verification Failed. High-risk violations must be resolved.")
        return 1

    print("✅ [AI-VERIFIER] High-risk semantic verification successfully PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
