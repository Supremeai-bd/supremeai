#!/usr/bin/env python3
"""Generate docs/generated/STATUS_PROOF.md and ENFORCE STATUS.md truthfulness.

বাংলা নীতি (False-Assurance doctrine):
- এই generator প্রতিটি machine-checkable দাবিকে প্রকৃত tree-এর বিরুদ্ধে যাচাই করে।
  কোনো দাবি tree-এর সাথে না মিললে exit 1 — CI লাল হবে, চুপচাপ সবুজ হবে না।
- আউটপুট সম্পূর্ণ deterministic (timestamp/sha/runtime ডেটা নিষিদ্ধ) যাতে
  `git diff --exit-code` diff-gate অর্থবহ থাকে। Runtime প্রমাণ (CI run, live probe)
  ইচ্ছাকৃতভাবে কমিট হয় না — সেগুলো Actions run summary-তে থাকে।
- Stdlib-only: CI-এর drift step নিরাপদে চালাতে পারে (কোনো তৃতীয়-পক্ষ dep নেই)।
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATUS_MD = REPO / "STATUS.md"
PROOF_PATH = REPO / "docs" / "generated" / "STATUS_PROOF.md"
ROUTE_INVENTORY = REPO / "docs" / "generated" / "route_inventory.json"

CLAIM_BLOCK_RE = re.compile(r"<!--\s*STATUS-PROOF:CHECK.*?\n(.*?)-->", re.DOTALL)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def fail(msg: str) -> None:
    # বাংলা: প্রতিটি ব্যর্থতা দৃশ্যমান হতে হবে — নীরব পাস নিষিদ্ধ।
    print(f"::error::STATUS-PROOF: {msg}")
    FAILURES.append(msg)


FAILURES: list[str] = []


def count_mission_tests() -> int:
    """AST দিয়ে backend/tests/missions/test_*.py-র test function গণনা (সঠিক, অনুমান নয়)।"""
    total = 0
    for path in sorted((REPO / "backend" / "tests" / "missions").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        total += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
    return total


def count_frontend_test_files() -> int:
    """vitest-এর include চুক্তির সাথে হুবহু মিলিয়ে src/**/*.{test,spec}.{ts,tsx} গণনা।"""
    src = REPO / "frontend" / "src"
    patterns = ("*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx")
    return sum(1 for pat in patterns for _ in src.rglob(pat))


def count_frontend_e2e_specs() -> int:
    """Playwright E2E spec গণনা (frontend/e2e/*.spec.ts) — vitest-এর বাইরে, আলাদা সত্য।"""
    return len(list((REPO / "frontend" / "e2e").glob("*.spec.ts")))


def read_route_count() -> int:
    data = json.loads(ROUTE_INVENTORY.read_text(encoding="utf-8"))
    return int(data["route_count"])


def parse_claims() -> dict[str, str]:
    match = CLAIM_BLOCK_RE.search(STATUS_MD.read_text(encoding="utf-8"))
    if not match:
        fail("STATUS.md এ STATUS-PROOF:CHECK ব্লক পাওয়া যায়নি — মেশিন-চেক চুক্তি ভাঙা")
        return {}
    claims: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            if re.fullmatch(r"[a-z0-9_]+", key.strip()):
                claims[key.strip()] = value.strip()
    return claims


def verify_links() -> list[str]:
    """STATUS.md-এর প্রতিটি repo-relative লিংক প্রকৃত ফাইল/ডিরেক্টরিতে আছে কি না।"""
    results: list[str] = []
    for target in sorted(set(LINK_RE.findall(STATUS_MD.read_text(encoding="utf-8")))):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#")[0]
        if not path:
            continue
        exists = (REPO / path).exists()
        results.append(
            f"- [{'x' if exists else ' '}] `{path}` — "
            + ("exists" if exists else "**MISSING**")
        )
        if not exists:
            fail(f"STATUS.md লিংক-টার্গেট নেই: {path}")
    return results


# বাংলা: deployment verification chain-এর static inventory — কোন ফাইলে কী গেট আছে।
# টেক্সট-মার্কার স্ক্যান ব্যবহার করা হয়েছে (stdlib-only; yaml dep সচেতনভাবে এড়ানো)।
CHAIN_FILES = {
    ".github/workflows/ci-deploy-production.yml": {
        "kind": "reusable deploy (workflow_call)",
        "markers": ["workflow_call", "Deploy Core to Render"],
    },
    ".github/workflows/09-post-deploy-smoke.yml": {
        "kind": "post-deploy Playwright canary (workflow_run)",
        # Marker updated with the 2026-09-19 URL-contract fix: the canary
        # targets the FRONTEND surface (FRONTEND_PRODUCTION_URL) with an
        # explicit backend health probe; the fail-closed UNVERIFIED path
        # must keep naming the unconfigured-secrets condition.
        "markers": [
            "Production Deploy",
            "FRONTEND_PRODUCTION_URL / PRODUCTION_URL secrets are not configured",
        ],
    },
    ".github/workflows/qa-live-smoke.yml": {
        "kind": "scheduled live probe (schedule + workflow_dispatch)",
        "markers": ["PRODUCTION_URL is not configured", "api/v1/health/live"],
    },
}


def verify_chain() -> list[str]:
    lines: list[str] = []
    for rel, meta in CHAIN_FILES.items():
        path = REPO / rel
        if not path.exists():
            fail(f"verification-chain ফাইল অনুপস্থিত: {rel}")
            lines.append(f"- ❌ `{rel}` — MISSING (declared in generator, not in tree)")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [m for m in meta["markers"] if m not in text]
        if missing:
            fail(f"{rel}-এ fail-closed/চুক্তি মার্কার অনুপস্থিত: {missing}")
            lines.append(f"- ❌ `{rel}` — missing markers: {missing}")
        else:
            lines.append(
                f"- ✅ `{rel}` — {meta['kind']}; fail-closed gate markers present"
            )
    return lines


CLAIM_VERIFIERS = {
    "missions_tests": count_mission_tests,
    "frontend_test_files": count_frontend_test_files,
    "frontend_e2e_specs": count_frontend_e2e_specs,
    "registered_routes": read_route_count,
}


def main() -> int:
    claims = parse_claims()
    claim_lines: list[str] = []
    for key in sorted(claims):
        verifier = CLAIM_VERIFIERS.get(key)
        if verifier is None:
            fail(f"অজানা claim key '{key}' — verifier যোগ করুন বা দাবিটি বাদ দিন")
            claim_lines.append(f"- ❌ {key}={claims[key]} — no verifier")
            continue
        actual = verifier()
        claimed = int(claims[key])
        ok = actual == claimed
        if not ok:
            fail(f"{key}: STATUS.md দাবি {claimed}, tree-বাস্তব {actual}")
        claim_lines.append(
            f"- {'✅' if ok else '❌'} `{key}={claimed}` → tree reality: **{actual}**"
            + ("" if ok else "  ← দাবি ও বাস্তব মিলছে না")
        )

    link_lines = verify_links()
    chain_lines = verify_chain()

    # বাংলা: ব্যর্থ হলেও proof লেখা হয় (ব্যর্থতার রাষ্ট্রই প্রমাণ), তারপর exit 1 —
    # দুই দিক থেকেই লাল: কনটেন্ট দেখায় + diff-gate ও exit code ধরে।
    verdict = "PASS" if not FAILURES else "FAIL"
    lines = [
        "# STATUS_PROOF.md (generated — do not hand-edit)",
        "",
        f"**Verdict: {verdict}** — "
        + (
            "প্রতিটি machine-checkable দাবি tree-বাস্তবের সাথে মিলেছে।"
            if not FAILURES
            else f"{len(FAILURES)}টি দাবি tree-বাস্তবের সাথে মেলেনি — STATUS.md হয় সংশোধন করুন, নয়তো tree ঠিক করুন।"
        ),
        "",
        "generated_by: `scripts/ci/generate_status_proof.py` (stdlib-only, deterministic)",
        "honesty_contract: tree-pure — কোনো timestamp/sha/runtime ডেটা নেই (diff-gate বৈধ রাখতে);",
        "runtime/live প্রমাণ Actions run summary-তে (ইচ্ছাকৃতভাবে কমিট হয় না)।",
        "",
        "## Machine-verified claims (STATUS.md `STATUS-PROOF:CHECK` block)",
        "",
        *claim_lines,
        "",
        "## STATUS.md referenced repo paths",
        "",
        *link_lines,
        "",
        "## Deployment verification chain (static inventory)",
        "",
        *chain_lines,
        "",
        "Live/runtime evidence: CI Pipeline summaries, `QA — Live Production Smoke` run summaries",
        "(fail-closed যতক্ষণ না `vars.PRODUCTION_URL` কনফিগার করা হয়)।",
        "",
    ]
    PROOF_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROOF_PATH.write_text("\n".join(lines), encoding="utf-8")

    for failure in FAILURES:
        print(f"STATUS-PROOF FAIL: {failure}")
    print(f"STATUS_PROOF.md written ({verdict}, {len(FAILURES)} failures)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
